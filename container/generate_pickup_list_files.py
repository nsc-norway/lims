import sys
import re
import csv
import argparse
import string
from operator import itemgetter
from genologics.lims import *
from genologics import config
from collections import namedtuple

VERSO_PLACEHOLDER_NAME = "verso input file"
TUBES_PLACEHOLDER_NAME = "normal tubes pickup list"

VERSO_SUFFIX = '_verso_input_file.txt'
TUBES_SUFFIX = '_tubes_pickup_list.csv'

VERSO_COLUMNS = ["TubeId", "DestinationRack", "Row", "Column"]
TUBES_COLUMNS = ["Sample_Number", "Archive pos.", "Alt sample ID"]

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

Well = namedtuple('well_on_96', ['RC', 'Row', 'Column'])

ORIENTATION = 'column'

SAMPLE_ID_SEPARATOR = '-'


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


def well_on_96_plate(tally, orientation='column'):
    """
    Placement of samples on a 96 well plate in
    column order: A1, B1, ..., H1, B1, B2, ..., H2, ..., ..., A12, B12, ..., H12
    row order: A1, A2, ..., A12, B1, B2, ..., B12, ..., ..., H1, H2, ..., H12

    :tally: tally of sample, 1-based
    :orientation: ['column', 'row']
    :return: Well = namedtuple('well_on_96', ['RC', 'Row', 'Column'])
    """
    ROW_LETTERS = string.ascii_uppercase[:8]

    exhaust = 8 if orientation == 'column' else 12
    orient = (tally - 1) // exhaust + 1
    perpend = (tally - 1) % exhaust + 1

    def get_well(row, col):
        RC = ROW_LETTERS[row - 1] + str(col)  # A1, A2, B1, B2
        well = Well(RC, row, col)
        return well

    if orientation == 'column':
        well = get_well(perpend, orient)
    else:
        well = get_well(orient, perpend)

    return well


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

        verso_writer.writeheader()
        tubes_writer.writeheader()

        verso_rows = []
        verso_count = 0
        tubes_rows = []

        for smp, art in sorted(zip(samples, inputs), key=lambda x: getattr(x[0], 'name')):
            assert smp.name == art.name
            sample_name = smp.name

            sample_no = sample_name.split(SAMPLE_ID_SEPARATOR)[0]

            archive_pos = smp.udf.get('Archive position Diag')

            alt_sample_id = smp.udf.get('Alternative sample ID Diag')

            # tube and 96 well plate
            if art.location[0].type_name == '96 well plate':
                verso_count += 1
                well = well_on_96_plate(verso_count, orientation=ORIENTATION)
                row = {
                    "TubeId": sample_no,
                    "DestinationRack": 1,
                    "Row": well.Row,
                    "Column": well.Column
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
            for vr in verso_rows:  # already sorted by sample name
                verso_writer.writerow(vr)

        if tubes_rows:
            tubes_rows = sorted(tubes_rows, key=itemgetter('Archive pos.'))
            for tr in tubes_rows:
                tubes_writer.writerow(tr)


if __name__ == "__main__":
    sys.exit(main())
