# Locate where the script is used in workflows

from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

if len(sys.argv) == 1 or sys.argv[1].startswith("-"):
    print "usage: find-script-usage.py SCRIPT_NAME [--active]"
    print ""
    print "   SCRIPT_NAME: search term (any substring of command line)"
    print "   --active: only show active workflows"
    print ""
    sys.exit(1)

script_name = sys.argv[1]
show_active_only = len(sys.argv) > 2 and sys.argv[2] == "--active"

for workflow in lims.get_workflows():
    if not show_active_only or workflow.status == "ACTIVE":
        for stage in workflow.stages:
            if stage.step:
                stage.step.get()
                processtype_uri = stage.step.root.find('process-type').attrib['uri']
                processtype_xml = lims.get(processtype_uri)
                matches = []
                for parameter in processtype_xml.findall('parameter'):
                    command = parameter.find('string').text
                    if script_name in command:
                        matches.append(parameter.attrib['name'])
                if matches:
                    print "MATCH:", workflow.status, "workflow:", workflow.name
                    print "      step:         ", stage.step.name
                    print "      processtype:  ", processtype_xml.attrib['name']
                    print "      automation(s):", ", ".join(matches)
                    print ""
