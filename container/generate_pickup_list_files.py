import sys
import re
import csv
import argparse
from operator import itemgetter
from genologics.lims import *
from genologics import config

VERSO_PLACEHOLDER_NAME = "verso input file"
TUBES_PLACEHOLDER_NAME = "normal tubes pickup list"

VERSO_SUFFIX = '_verso_input_file.csv'
TUBES_SUFFIX = '_tubes_pickup_list.csv'

VERSO_COLUMNS = ["Sample_Number"]
TUBES_COLUMNS = ["Sample_Number", "Archive pos.", "Alt sample ID"]

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


def look_up_target_id(art_ids, art_name):
    """
    look for the correct artifact id
    """
    ids = art_ids.strip().split()
    for i in ids:
        art = Artifact(lims, id=i)
        if art.name == art_name:
            return i
    else:
        raise RuntimeError('No file placeholder named "{}" among ids: {}'
                           ''.format(art_name, ' '.join(art_ids)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", required=True)
    parser.add_argument("--file_ids", required=True)
    args = parser.parse_args()

    process_id = args.pid
    file_ids = args.file_ids

    process = Process(lims, id=process_id)

    inputs = process.all_inputs()
    lims.get_batch(inputs)

    samples = [input.samples[0] for input in inputs]
    lims.get_batch(samples)

    file_id_verso = look_up_target_id(file_ids, VERSO_PLACEHOLDER_NAME)
    file_id_tubes = look_up_target_id(file_ids, TUBES_PLACEHOLDER_NAME)

    verso_filename = file_id_verso + VERSO_SUFFIX
    tubes_filename = file_id_tubes + TUBES_SUFFIX

    with (
            open(verso_filename, 'w')) as verso_fd, (
            open(tubes_filename, 'w')) as tubes_fd:

        verso_writer = csv.DictWriter(verso_fd, VERSO_COLUMNS, delimiter=';', lineterminator='\n')
        tubes_writer = csv.DictWriter(tubes_fd, TUBES_COLUMNS, delimiter=';', lineterminator='\n')

        # verso_writer.writeheader()
        tubes_writer.writeheader()

        verso_rows = []
        tubes_rows = []

        for art, smp in zip(inputs, samples):
            sample_name = smp.name

            sample_no = re.match(r"([0-9]+)-", sample_name)
            sample_no = sample_no.group(1) if sample_no else sample_name

            archive_pos = smp.udf.get('Archive position Diag')

            alt_sample_id = smp.udf.get('Alternative sample ID Diag')

            # tube and 96 well plate
            if art.location[0].type_name == '96 well plate':
                row = {
                    "Sample_Number": sample_no
                }
                verso_rows.append(row)
            else:
                row = {
                    "Sample_Number": sample_no,
                    "Archive pos.": archive_pos,
                    "Alt sample ID": alt_sample_id,
                }
                tubes_rows.append(row)

        if verso_rows:
            verso_rows = sorted(verso_rows, key=itemgetter('Sample_Number'))
            for vr in verso_rows:
                verso_writer.writerow(vr)

        if tubes_rows:
            tubes_rows = sorted(tubes_rows, key=itemgetter('Archive pos.'))
            for tr in tubes_rows:
                tubes_writer.writerow(tr)


if __name__ == "__main__":
    sys.exit(main())
