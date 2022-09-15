# -*- coding: utf-8 -*-
import sys
import re
import csv
import argparse
import string
from datetime import datetime
from operator import itemgetter
from genologics.lims import *
from genologics import config
from collections import namedtuple

VERSO_PLACEHOLDER_NAME = "verso input file"
TUBES_PLACEHOLDER_NAME = "normal tubes pickup list"

VERSO_SUFFIX = 'verso.txt'
TUBES_SUFFIX = '_tubes_pickup_list.csv'

VERSO_COLUMNS = ["TubeId", "DestinationRack", "Row", "Column"]
TUBES_COLUMNS = [
    "Antall",
    "Pos Rack",
    "Rack",
    "Prøvenummer",
    "Arkivposisjon",
    "Alternative Sample ID",
    "Konsentrasjon ng/µL",
    "µL EB",
    "µL DNA"
]

ENHET_MAP = {
    "diag-ekg": "EKG",
    "diag-excap": "EHD",
    "diag-wgs": "EHD",
    "diag-ehg": "EHG"
}

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

Well = namedtuple('well_on_96', ['RC', 'Row', 'Column'])

ORIENTATION = 'column'
SAMPLE_ID_SEPARATOR = '-'
SAMPLE_ID_MATCHER = re.compile(r'^(\d{11}|[A-Z]{2}\d{8})')


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


def id_from_name(name):
    """get sample ID from sample name"""
    id_matching = SAMPLE_ID_MATCHER.match(name)
    # starts with 11 digits or 2 letter and 8 digits
    if id_matching:
        sample_id = id_matching.group()
    else:
        sample_id = name.split(SAMPLE_ID_SEPARATOR)[0]

    return sample_id


def get_enhet(artifacts):
    """get the enhet to be added to verso input file name"""

    enhet = 'UNKNOWN'

    for art in artifacts:
        if art.location[0].type_name == '96 well plate':
            projname = art.samples[0].project.name
            for k, v in ENHET_MAP.items():
                if projname.lower().startswith(k):
                    enhet = v
                    break
            else:
                continue
            break

    return enhet


def get_username(process):
    """get username of process to be added to verso input file name"""

    username = process.technician.username

    if username:
        return username
    else:
        return "UNKNOWN"


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

    enhet = get_enhet(inputs)
    username = get_username(process)
    file_date = datetime.strftime(datetime.today(), "%m%d%y")
    verso_filename = "_".join([file_id_verso, enhet.upper(), username.upper(), file_date,
                               VERSO_SUFFIX])

    tubes_filename = file_id_tubes + TUBES_SUFFIX

    with (
            open(verso_filename, 'w',)) as verso_fd, (
            open(tubes_filename, 'w', encoding='utf-16')) as tubes_fd:

        verso_writer = csv.DictWriter(verso_fd, VERSO_COLUMNS, delimiter=';', lineterminator='\n')
        tubes_writer = csv.DictWriter(tubes_fd, TUBES_COLUMNS, delimiter='\t', lineterminator='\n')

        verso_writer.writeheader()
        tubes_writer.writeheader()

        verso_rows = []
        verso_count = 0
        tube_counter = 0
        tubes_rows = []

        for smp, art in sorted(zip(samples, inputs), key=lambda x: getattr(x[0], 'name')):
            assert smp.name == art.name

            sample_name = smp.name
            sample_id = id_from_name(sample_name)

            # Arkivposisjon
            archive_pos = smp.udf.get('Archive position Diag')

            # Alternative Sample ID
            alt_sample_id = smp.udf.get('Alternative sample ID Diag')

            # Konsentrasjon, ul_EB, ul_DNA
            try:
                conc = smp.udf['Sample conc. (ng/ul)']
                if conc >= 9 and conc <= 180:
                    ul_EB = 43
                    ul_DNA = 2
                else:
                    # Compute 3 ng/uL in 45 uL total volume
                    if conc == 0.0:
                        sample_vol = 2
                    else:
                        sample_vol = (3 * 45) / conc
                    ul_EB = max(0, 45 - sample_vol)
                    ul_DNA = sample_vol
            except KeyError:
                conc = "UKJENT"
                ul_EB = "UKJENT"
                ul_DNA = "UKJENT"

            # tube and 96 well plate
            if art.location[0].type_name == '96 well plate':
                verso_count += 1
                well = well_on_96_plate(verso_count, orientation=ORIENTATION)
                row = {
                    "TubeId": sample_id,
                    "DestinationRack": 1,
                    "Row": well.Row,
                    "Column": well.Column
                }
                verso_rows.append(row)
            else:
                labware = "Rack%d" % ((tube_counter // 32) + 1)
                position_id = str((tube_counter % 32) + 1)
                tube_counter += 1

                row = {
                    "Antall": tube_counter,
                    "Pos Rack": position_id,
                    "Rack": labware,
                    "Prøvenummer": sample_id,
                    "Arkivposisjon": archive_pos,
                    "Alternative Sample ID": alt_sample_id,
                    "Konsentrasjon ng/µL": conc,
                    "µL EB": ul_EB,
                    "µL DNA": ul_DNA
                }
                tubes_rows.append(row)

        if verso_rows:
            for vr in verso_rows:  # already sorted by sample name
                verso_writer.writerow(vr)

        if tubes_rows:
            tubes_rows = sorted(tubes_rows, key=itemgetter('Prøvenummer'))
            for tr in tubes_rows:
                tubes_writer.writerow(tr)


if __name__ == "__main__":
    sys.exit(main())
