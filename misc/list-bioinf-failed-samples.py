from genologics.lims import *
from genologics import config
import datetime
import sys
import re

# This script lists the samples that have undergone Bioinfo QC Fail step.

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

qc_fail_processes = lims.get_processes(type="Bioinformatic QC fail_diag 1.4")

for qc_fail_proc in qc_fail_processes:
    artifacts = qc_fail_proc.all_inputs(unique=True)
    fail_date = qc_fail_proc.date_run
    for artifact in artifacts:
        assert len(artifact.samples) == 1
        sample = artifact.samples[0]
        print("\t".join([str(fail_date), sample.project.name, sample.name, artifact.udf.get('Bioinfo QC Failed Description Diag', '')]))


