# this
import logging
import sys

from genologics import config
from genologics.lims import *

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

LOAD_LIBRARY_TUBE_PROCESS_TYPE = "Load to Library Tube Strip NovaSeqX AMG 2.0"
RE_DEMULTIPLEX_WORKFLOW = "Re-demultiplex NovaSeq X run"

SETTINGS = [
    "Read 1 Cycles",
    "Read 2 Cycles",
    "Index 1 Cycles",
    "Index 2 Cycles",
    "NovaSeq X Instrument",
    "FASTQ Compression Format",
    "Run Name"
]


def fill_original_novx_settings(sample_sheet_process):
    # Get the input Analyte artifact, corresponding to lanes of the flow cell
    input_lanes = sample_sheet_process.all_inputs()

    if not all(
        la.parent_process
        and la.parent_process.type_name == LOAD_LIBRARY_TUBE_PROCESS_TYPE
        for la in input_lanes
    ):
        logging.error(
            "Can only add '%s' step's DERIVED SAMPLES to %s workflow.\n\nStep will be aborted!",
            LOAD_LIBRARY_TUBE_PROCESS_TYPE,
            RE_DEMULTIPLEX_WORKFLOW,
        )
        sys.exit(1)

    # the original setting process
    load_tube_process = input_lanes[0].parent_process

    for setting in SETTINGS:
        try:
            original = load_tube_process.udf[setting]
            if original is not None:
                sample_sheet_process.udf[setting] = original
        except KeyError:
            pass

    # default to demultiplexing only
    sample_sheet_process.udf["Demultiplexing Only"] = True

    sample_sheet_process.put()


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print(f"Usage: {sys.argv[0]} PROCESS_ID")
        sys.exit(1)

    process_id = sys.argv[1]

    process = Process(lims, id=process_id)

    fill_original_novx_settings(process)
