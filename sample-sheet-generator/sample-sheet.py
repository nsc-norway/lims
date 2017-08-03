# -----------------------------------
# NSC Sample Sheet Generation Tool
# -----------------------------------
# This may be used instead of the sample sheet generator that
# is bundled with Clarity LIMS. It produces sample sheets in a
# format readable by bcl2fastq.

# This tools is only designed to create sample sheets for 
# bcl2fastq2, for the NSC-specific file and directory names.
# It needs access to the run-ID to generate these names, so it 
# can't be run before the sequencing run is started.

# ** Project file structure (NSC) **

# DIRECTORY NAME (HiSeq 2500/4000/X):
# <RunIdText>.Project_<ProjectName>/Sample_<SampleName>

# DIRECTORY NAME (Mi/NextSeq):
# <RunIdText>.Project_<ProjectName>/

# FILE NAME (HiSeq 2500):
# <SampleName>_<SampleIndexSequence>_L00<LaneNumber>_R<ReadNumber>_001.fastq.gz
# ex. TEST_GACTAGTA_L002_R2_001.fastq.gz

# FILE NAME (All except HiSeq 2500):
# <SampleName>_S<SampleSheetOrdinal>_R<ReadNumber>_001.fastq.gz
# ex. 7-IPF1-2k_S7_R1_001.fastq.gz


# The sample sheet contains sections delimited by keywords in 
# square brackets, e.g. [Data]. Because it is a CSV file, it 
# MAY have an equal number of commas on all lines, so the section
# header would be "[Data],,,,,," (This happens if it is edited in
# Excel, and then it remains a valid sample sheet).

# ** Format overview **
#

#


import sys
from genologics.lims import *
from genologics import config

def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    step = Step(lims, id=process_id)
    containers = set(step.placements.get_selected_containers())
    if len(containers) > 1:
        lims.get_batch(containers)
    all_known = lims.get_containers(name=(container.name for container in containers))
    if len(all_known) > len(containers):
        pre_existing = set(all_known) - containers
        print "Containers with these names already exist in the system:",\
                ", ".join(container.name for container in pre_existing)
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1])

