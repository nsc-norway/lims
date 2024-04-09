from genologics.lims import *
from genologics import config
import sys

# Update root artifact names to the sample names
# This should be run as a project-level automation.
# Usage:
# python3 fix-sample-names.py PROJECT_ID

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

project = Project(lims, sys.argv[1])
samples = lims.get_samples(projectlimsid="BJR3060")
lims.get_batch(samples)
lims.get_batch(sample.artifact for sample in samples)
changed = []
for sample in samples:
    artifact = sample.artifact.stateless
    if artifact.name != sample.name:
        artifact.name = sample.name
        changed.append(artifact)

lims.put_batch(changed)

