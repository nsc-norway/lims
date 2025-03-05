#!/usr/bin/env python

from __future__ import print_function
import argparse
import sys
import os
import requests
import tempfile
import re
from genologics.lims import *
from genologics.entities import Process, Artifact
from genologics.config import USERNAME, PASSWORD, BASEURI


DEFAULT_CONTAINER = '96 well plate'
SCANNER_FILE_DELIMITER = ','
FILE_PLACEHOLDER_NAME = 'plate scanner output file'

SAMPLE_ID_SEPARATOR = '-'
SAMPLE_ID_MATCHER = re.compile(r'^(\d{11}|[A-Z]{2}\d{8})')

lims = Lims(BASEURI, USERNAME, PASSWORD)


def get_container_type(name):
    """
    Containertype whose name matches name
    """

    container_type = None

    match_con_types = lims.get_container_types(name=name)

    if match_con_types:
        container_type = match_con_types[0]

    return container_type


def read_layout(layout_file):
    """
    read a plate layout file
    """
    layout = dict()
    total_columns = 0

    def format_well(well):
        """
        scanner output well is like A01, B01, G12, reformat to A:1, B:1, G:12
        """
        match1 = re.match(r'[A-H]:\d{1,2}$', well)
        match2 = re.match(r'(?P<row>[A-H])(?P<col>\d{1,2})$', well)

        if match1:  # already well formatted
            return well
        elif match2:
            row_col = match2.groupdict()
            row = row_col['row']
            col = int(row_col['col'])
            return ':'.join([row, str(col)])
        else:
            raise RuntimeError(
                "Bad format of well position '{}' in the scanner output file!".format(well))

    with open(layout_file) as lf:
        line = lf.readline()  # header line
        total_columns = len(line.strip().split(SCANNER_FILE_DELIMITER))
        for l in lf:
            parts = l.strip().split(SCANNER_FILE_DELIMITER)
            if total_columns >= 3:
                plate_id = parts[0]
                well = parts[1]
                sample = parts[2]
            else:
                plate_id = None
                well = parts[0]
                sample = parts[1]

            # if plate_id is missing, give an error message
            if not plate_id:
                raise RuntimeError("Plate ID is missing in the scanner output file! The plate may have been turned around and scanned the wrong way.")

            # if not 2D tube, sample(TubeID) is empty
            if sample:
                well = format_well(well)
                layout[sample] = well

    return plate_id, layout


def look_up_target_id(art_ids):
    """
    look for the correct artifact id
    """
    ids = art_ids.strip().split()
    for i in ids:
        art = Artifact(lims, id=i)
        if art.name == FILE_PLACEHOLDER_NAME:
            return i

    return None


def download_file(art_id):
    """
    art_id: {compoundOutputFileLuid0}
    """

    file_artifact = Artifact(lims, id=art_id)  # file artifact
    files = file_artifact.files

    if not files:  # no file attached at step setup
        return None

    real_file = file_artifact.files[0]  # file endpoint

    download_url = real_file.uri + "/download"
    fileGET = requests.get(download_url, auth=(USERNAME, PASSWORD))

    # write to a temp file
    with tempfile.NamedTemporaryFile(delete=False) as fd:
        for chunk in fileGET.iter_content():
            fd.write(chunk)

    return fd.name


def id_from_name(name):
    """get sample ID from sample name"""
    id_matching = SAMPLE_ID_MATCHER.match(name)
    # starts with 11 digits or 2 letter and 8 digits
    if id_matching:
        sample_id = id_matching.group()
    else:
        sample_id = name.split(SAMPLE_ID_SEPARATOR)[0]

    return sample_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", required=True)
    parser.add_argument("--file_ids", required=True)
    args = parser.parse_args()

    processLuid = args.pid
    file_ids = args.file_ids

    target_id = look_up_target_id(file_ids)

    if not target_id:
        raise RuntimeError("Could not find the file placeholder for '{}'"
                           "".format(FILE_PLACEHOLDER_NAME))

    layout_file_path = download_file(target_id)

    if not layout_file_path:  # no file was attached
        # print("no scanner file attached", file=sys.stderr)
        # return
        raise RuntimeError("Plate scanner file not uploaded!")

    new_container_name, layout = read_layout(layout_file_path)

    os.remove(layout_file_path)

    proc = Process(lims, id=processLuid)
    step = proc.step

    # destination container
    new_container = lims.create_container(get_container_type(DEFAULT_CONTAINER),
                                          name=new_container_name)

    placements = step.placements.get_placement_list()

    # destination placements
    payload_placements = []

    for pl in placements:
        art = pl[0]
        sample_id = id_from_name(art.name)
        if sample_id in layout:
            placement = [art, (new_container, layout[sample_id])]
            payload_placements.append(placement)

    # if no sample in scanner file, exit explicitly, otherwise placement screen is gone in Clarity
    if not payload_placements:
        return

    step.placements.set_placement_list(payload_placements)

    step.placements.post()


if __name__ == '__main__':
    sys.exit(main())
