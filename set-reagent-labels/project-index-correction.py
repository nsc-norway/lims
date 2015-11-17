#!/bin/env python

# Index correction script for all derived samples in a project.

# Usage: First correct the Index requested/used UDF for all submitted samples.
# Then run this command:
# python project-index-correction.py <name_of_project> [index_category]

# Optionally specify index category, or the auto-detection function will be used.

import sys

from genologics.lims import *
from genologics import config

import indexes

SAMPLE_INDEX_UDF = "Index requested/used"

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

project = lims.get_projects(name=sys.argv[1])[0]


samples = lims.get_samples(projectlimsid=project.id)

# First get the correct reagent labels
reagents = indexes.get_all_reagent_types()

index_name = [(sample.udf[SAMPLE_INDEX_UDF], sample.name) for sample in samples]

if len(sys.argv) > 2:
    result = indexes.get_reagents_for_category(reagents, index_name, sys.argv[2])
else:
    category, result = indexes.get_reagents_auto_category(reagents, index_name)
    print "Auto-detected index category:", category

replace_map = {}
pools = set()

for sample, new_reagent in zip(samples, result):
    analytes = lims.get_artifacts(type='Analyte', samplelimsid=sample.id)
    print "Processing", len(analytes), "derived samples of", sample.name, "(" + sample.id + ")"

    updated = 0

    for analyte in analytes:
        num = len(analyte.reagent_labels)
        if num == 1:
            old_reagent = next(iter(analyte.reagent_labels))
            if old_reagent != new_reagent:
                analyte.reagent_labels.clear()
                analyte.reagent_labels.add(new_reagent)
                analyte.put()
                print " Updated analyte", analyte.name, "(" + analyte.id + "):"
                print "   ", old_reagent, "->", new_reagent
                replace_map[old_reagent] = new_reagent
        elif num > 1:
              pools.add(analyte)
    print ""

for pool in pools:
    print "Processing pool", pool.name
    updated = 0
    to_add = set()
    for old, new in replace_map.items():
        try:
            pool.reagent_labels.remove(old)
            to_add.add(new)
            updated += 1
        except KeyError:
            continue
    if updated:
        for reagent_label in to_add:
            pool.reagent_labels.add(reagent_label)
        pool.put()
    print " Updated", updated, "reagents in the pool"
    print ""

