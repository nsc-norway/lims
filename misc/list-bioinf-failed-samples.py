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
        bi_processes = lims.get_processes(inputartifactlimsid=artifact.id, type="Bioinformatic processing_diag 1.4")
        texts = []
        for bi_process in sorted(bi_processes, key=lambda proc: proc.date_run or ""):
            artifact_qc_out = [
                    o['uri'] for i, o in bi_process.input_output_maps
                    if o['output-generation-type'] == 'PerInput' and i['limsid'] == artifact.id
            ]
            assert len(artifact_qc_out) == 1
            texts.append(artifact_qc_out[0].udf.get('Bioinfo QC Failed Description Diag', "NULL").replace('"', "'"))
        print("\t".join([str(fail_date), sample.project.name, sample.name, " | ".join(texts)]))


