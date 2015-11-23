# Assign inputs of a given process to workflow

import sys
import re
from genologics.lims import *
from genologics import config

def main():
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    projects = lims.get_projects()
    #lims.get_batch(projects)
    exome_project_ids = [
            project.id
            for project in projects
            if project.name.find("excap") != -1 and not project.name.startswith("Sun-")
            ]

    exome_samples = len(lims.get_samples(projectlimsid=exome_project_ids))

    print "Number of exome samples (not Sun): ", exome_samples


main()

