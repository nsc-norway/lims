from genologics.lims import *
from genologics import config
import sys

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} PROCESS_ID")
    sys.exit(1)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

process = Process(lims, id=sys.argv[1])

required_fields = ['Spike-in %', 'Molarity (nM)']
projects_to_put = set()
for output in process.all_outputs(unique=True):
    for field in required_fields:
        if field not in output.udf:
            print("Error: '{}' is required, but not specified for pool '{}'. Please go back to Record Details and set it.".format(field, output.name))
            sys.exit(1)
    for sample in lims.get_batch(output.samples):
        projects_to_put.add(sample.project)

for project in projects_to_put:
    project.udf['Project type'] = "Microbiology"
    project.udf['Delivery method'] = "User HDD"
    project.udf['Sample type'] = "gDNA"
    project.udf["Evaluation type"] = "None"
    project.udf["Contact email"] = "UXKAVG@ous-hf.no; aingebre@ous-hf.no; uxriva@ous-hf.no; mahagb@ous-hf.no; cflad@ous-hf.no; siqliu@ous-hf.no"
    project.udf["Contact person"] = "Gunilla Løvgården, Andre Ingebretsen, Marie Elisabeth Vad, Mari Elisabeth Sørås Hagbø, Cathrine Fladeby, Siqing Liu"
    project.udf["Contact institution"] = "Molekylærbiologisk seksjon"
    project.put()

