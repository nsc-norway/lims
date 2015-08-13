#!/bin/env python

# Change index sequences in all derived samples 

# Use:
# python index-correction.py <corrected_sample_sheet> [index category]


# Using old-style HiSeq sample sheet as input

import sys

from genologics.lims import *
from genologics import config

import indexes

SAMPLE_INDEX_UDF = "Index requested/used"

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


sample_sheet_lines = open(sys.argv[1]).readlines()
header = [kw.lower().replace("_", "") for kw in sample_sheet_lines[0].strip("\n").split(",")]
col = dict((h_col, i) for i, h_col in enumerate(header))

sample_sheet_data = [l.strip("\n").split(",") for l in sample_sheet_lines[1:]]

reagents = indexes.get_all_reagent_types()
index_analyte = [(e[col['index']], e[col['sampleid']]) for e in sample_sheet_data]
if len(sys.argv) > 2:
    result = indexes.get_reagents_for_category(reagents, index_analyte, sys.argv[2])
else:
    category, result = indexes.get_reagents_auto_category(reagents, index_analyte)
    print "Auto-detected index category:", category


for entry, new_reagent in zip(sample_sheet_data, result):
    top_analyte = Artifact(lims, id=entry[col['description']])
    old_reagent_label = next(iter(top_analyte.reagent_labels))
    old_index = old_reagent_label.index_sequence
    new_index = entry['index']

    # First correct the submitted samples
    sample = top_analyte.samples[0]
    if not sample.udf[SAMPLE_INDEX_UDF] in [new_index, old_index]:
        print "Error: Sample", sample.name, "had unexpected index UDF (" + SAMPLE_INDEX_UDF + "):",\
                sample.udf[SAMPLE_INDEX_UDF]
        sys.exit(1)
    sample.udf[SAMPLE_INDEX_UDF] = new_index
    sample.put()

    analytes = lims.get_artifacts(samplelimsid=sample.id)

    for analyte in analytes:
        if analyte.reagent_labels:
            rl = next(iter(analyte.reagent_labels))
            if rl == old_reagent_label:
                analyte.reagent_labels.clear()
                analyte.reagent_labels.add(new_reagent)
                analyte.put()
                print "Corrected analyte", analyte.name, "(" + analyte.id + ")"
            elif rl != new_reagent:
                print "Error: Analyte", analyte.name, "(" + analyte.id + ") has unexpected reagent type", rl
                sys.exit(1)


