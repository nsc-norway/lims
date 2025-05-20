
import logging
import os
import sys

import lib.demultiplexing
from genologics import config
from genologics.lims import *

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


MINIMUM_MISMATCH_THRESHOLD = 3

def get_index_sequences(lims, reagent_label_list):
    """Convert reagent label names (strings) into tuples of (index1, index2) by looking up the sequences
    in LIMS. Empty strings are used if there is no index."""

    logging.info("Retrieving index sequences from LIMS API.")

    # First retrieve all reagent labels, using batches to avoid URL size limit
    reagent_types = []
    BATCH_SIZE = 100
    for batch_start in range(0, len(reagent_label_list), BATCH_SIZE):
        reagent_types += lims.get_reagent_types(
            name=[
                name
                for name in reagent_label_list[batch_start : (batch_start + BATCH_SIZE)]
                if name
            ]
        )

    # This will fetch all reagent types from API one by one, by querying for the "name" property
    reagent_type_map = {rt.name: rt for rt in reagent_types}

    result_index_list = []
    for reagent_label in reagent_label_list:
        if not reagent_label:
            result_index_list.append(("", ""))
        else:
            if reagent_label in reagent_type_map:
                seq_parts = reagent_type_map[reagent_label].sequence.split("-")
                if len(seq_parts) == 1:  # Single index
                    result_index_list.append((seq_parts[0], ""))
                elif len(seq_parts) == 2:  # Dual index
                    result_index_list.append(tuple(seq_parts))
                else:
                    raise ValueError(
                        f"Reagent type {reagent_label} has malformed sequence in LIMS: {reagent_type_map[reagent_label].sequence}."
                    )
            else:
                raise ValueError(
                    f"Reagent type {reagent_label} referenced in artifact but does not exist."
                )

    return result_index_list


def hamming_distance(seq1, seq2):
    """Hamming distance between two strings.
    
    If the length is different, only the shortest length with be used for distances."""

    return sum(c1 != c2 for c1, c2 in zip(seq1, seq2))


def check_indexes_main(process, check_index_1, check_index_2):

    logging.info(f"Checking indexes config: index1: {check_index_1}, index2: {check_index_2}")

    # This script is designed to run on a pooling step, so we check indexes in all pools
    output_artifacts = process.all_outputs(unique=True, resolve=True)
    pool_artifacts = [o for o in output_artifacts if o.type == 'Analyte']

    check_index_reads = []
    if check_index_1: check_index_reads.append(1)
    if check_index_2: check_index_reads.append(2)

    failing_pools = {}

    for pool_artifact in sorted(
        pool_artifacts, key=lambda artifact: artifact.location[1][0]
    ):
        logging.info(f"Processing pool {pool_artifact.name}.")

        # Get the demux endpoint for this pool and process the XML entities
        # Getting a list of [(sample, artifact, reagent_label_name), ...]
        demux_list = lib.demultiplexing.get_demux_artifact(lims, pool_artifact)

        # Convert reagent label name into a tuple of (index1, index2) sequences
        index_pairs = get_index_sequences(
            lims, [reagent_label_name for _, _, reagent_label_name in demux_list]
        )
        sample_names = [sample.name for sample, _, _ in demux_list]
        # (name, (index1, index2))
        sample_index_tuples = zip(sample_names, index_pairs)
        
        # Compute all against all distances
        for index_read in check_index_reads:
            logging.info(f"Processing index read {index_read}.")
            for i, (name, indexes) in enumerate(sample_index_tuples):
                for other_name, other_indexes in sample_index_tuples[i + 1 :]:
                    index_seq = indexes[index_read - 1]
                    other_index_seq = other_indexes[index_read - 1]
                    mismatches = hamming_distance(index_seq, other_index_seq)

                    if mismatches < MINIMUM_MISMATCH_THRESHOLD:
                        logging.error(f"Sample '{sample}' and '{other_sample}' insufficient mismatches in index read {index_read}.")
                        logging.error(f"Index '{index_seq}' and '{other_index_seq}' have {mismatches} mismatches but {MINIMUM_MISMATCH_THRESHOLD} is required.")
                        failing_pools[pool_artifact.id] = pool_artifact.name

    if failing_pools:
        logging.error("Index compatibility issues in pool(s): " + ", ".join(str(l) for l in failing_pools.values()) + " - see log.")
        sys.exit(1)
    else:
        logging.info("Index compatibility check OK.")
        sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) < 5:
        
        print(
            f"Usage: {sys.argv[0]} process output_file_name check_index_1 check_index_2"
        )
        sys.exit(1)

    process = Process(lims, id=sys.argv[1])
    output_file_name = sys.argv[2]
    check_index_1 = bool(sys.argv[3])
    check_index_2 = bool(sys.argv[4])

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level, filename=output_file_name)

    check_indexes_main(process, check_index_1, check_index_2)

