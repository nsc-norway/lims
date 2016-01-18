# Fill in read-only UDFs for run (sequencing) process
from __future__ import print_function
import sys
from functools import partial
import datetime
import random
from genologics.lims import *
from genologics import config


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    
    UDF = [
            ('Finish Date', datetime.date.today(), lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date()),
            ('Run Type', 'Paired End Dual Indexing Run', str),
            ('Status', 'Cycle 259 of 268', str),
            ('Control Lane', '', str),
            ('Flow Cell ID', '', str),
            ('Flow Cell Version', 'HiSeq Flow Cell v4', str),
            ('Flow Cell Position', 'A', str),
            ('Experiment Name', '', str),
            ('Read 1 Cycles', 126, int),
            ('Index 1 Read Cycles', 8, int),
            ('Index 2 Read Cycles', 8, int),
            ('Read 2 Cycles', 126, int),
            ('Output Folder', 'X:\\', str),
            ('Run ID', '', str),
            ('TruSeq SBS Kit Type', 'TruSeq SBS Kit-HS (200 cycles)', str),
            ('TruSeq SBS Kit lot #', '', str)
            ]

    for udfname, default, converter in UDF:
        try:
            old_val = process.udf[udfname]
            if old_val is not None:
                default = old_val
        except KeyError:
            old_val = None
        choice = raw_input(udfname + " [" + str(default) + "]:")
        process.udf[udfname] = (choice and converter(choice)) or default
        if process.udf[udfname] != old_val:
            process.put()


    LANE_UDF = [
            (['Yield PF (Gb) R1', 'Yield PF (Gb) R2'], 27.96),
            (['Cluster Density (K/mm^2) R1', 'Cluster Density (K/mm^2) R2'], 840),
            (['Clusters Raw R1', 'Clusters Raw R2'], 233254747),
            (['Clusters PF R1', 'Clusters PF R2'], 223658378),
            ('Loading Conc. (pM)', 19),
            ('% Bases >=Q30 R1', 92.4),
            ('% Bases >=Q30 R2', 89.4),
            (['%PF R1', '%PF R2'], 95.9),
            ('Intensity Cycle 1 R1', 9022),
            ('Intensity Cycle 1 R2', 3728),
            ('% Intensity Cycle 20 R1', 120.9),
            ('% Intensity Cycle 20 R2', 362.7),
            ('% Phasing R1', 0.062),
            ('% Phasing R2', 0.096),
            ('% Prephasing R1', 0.076),
            ('% Prephasing R2', 0.078),
            ('% Aligned R1', 1.4),
            ('% Aligned R2', 1.4),
            ('% Error Rate R1', 0.33),
            ('% Error Rate R2', 0.46),
            ]

    for lane in process.all_inputs(unique=True):
        for udfs, value in LANE_UDF:
            if isinstance(udfs, str):
                udfs = [udfs]
            for u in udfs:
                lane.udf[u] = value
        lane.put()


def normal(mean, stdev):
    return partial(random.normalvariate, mean, stdev)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        print("use: fake-run.py PROCESS_ID", file=sys.stderr)

