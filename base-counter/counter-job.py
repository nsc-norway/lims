#!/usr/bin/python

import glob
import os
import illuminate

DB_FILE = "/tmp/rundb.txt"
BASELINE_FILE = "/tmp/baseline.txt"
RATE_FILE = "/tmp/rate.txt"
RUN_STORAGE="/data/runScratch.boston"

def main():
    try:
        with open(DBFILE) as run_db_file:
            run_db = [l.split("\t") for l in run_db_file.readlines()]
    except IOError:
        run_db = []

    try:
        with open(BASELINE_FILE) as baseline_file:
            baseline = int(baseline_file.read())
    except IOError:
        baseline = 0

    rate = 0

    files = glob.glob(os.path.join(RUN_STORAGE, "*"))
    for path in files:
        run_type = get_cluster_density(path)

    with open(BASELINE_FILE) as baseline_file:
        baseline_file.write(str(baseline))

    with open(RATE_FILE) as rate_file:
        rate_file.write(str(rate))

def get_run_type(path):
    pass

def get_hiseq_miseq_clusters(path):
    pass


if __name__ == "__main__":
    main()

