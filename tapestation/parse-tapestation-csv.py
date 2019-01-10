# Parse TapeStation output file based on well position in the TS plate

from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

process = Process(lims, id=sys.argv[1])
file_artifact = Artifact(lims, id=sys.argv[2])

try:
    data = file_artifact.files[0].download()
except:
    print("CSV file not found.")
    sys.exit(1)

if not data:
    print("CSV file is empty.")
    sys.exit(2)


lines = data.decode('latin-1').splitlines()
header = lines[0].split(",")
try:
    wellid_col = header.index("WellId")
    average_size_col = header.index("Average Size [bp]")
    conc_col = header.index("Conc. [pg/µl]")
    region_molarity_col = header.index("Region Molarity [pmol/l]")
except ValueError as e:
    print("Missing column(s) in CSV file: ", e)
    sys.exit(3)

outputs = lims.get_batch(o['uri'] for i,o in process.input_output_maps if o['output-generation-type'] == "PerInput")
container_ids = set(output.location[0].id for output in outputs)

if len(container_ids) != 1:
    print("Exactly one output container is required, got", len(container_ids), ".")
    sys.exit(4)

well_artifact_map = {output.location[1].replace(":",""): output for output in outputs}
unprocessed_artifacts = set(output.id for output in outputs)
unmatched_locations_in_file = []

for i, line in enumerate(lines, 1):
    if line and i > 1:
        cells = line.split(",")
        try:
            wellid = cells[wellid_col]
            average_size = float(cells[average_size_col])
            conc = float(cells[conc_col])
            molarity = float(cells[region_molarity_col])
        except IndexError:
            print("Not enough columns at line", i, ".")
            sys.exit(5)
        except ValueError as e:
            print("Invalid data at line", i, ":", e)
            sys.exit(5)
        
        try:
            output = well_artifact_map[wellid]
            output.udf['Molarity'] = molarity / 1000.0
            output.udf['Concentration'] = conc / 1000.0
            output.udf['Average Fragment Size'] = average_size
            unprocessed_artifacts.remove(output.id)
        except KeyError:
            unmatched_locations_in_file.append(wellid)

lims.put_batch(outputs)
warnings = []
if unprocessed_artifacts:
    warnings.append("{} samples in LIMS were not found in the result file.".format(len(unprocessed_artifacts)))
if unmatched_locations_in_file:
    warnings.append("The output file contains samples at {} locations not found in LIMS.".format(
        len(unmatched_locations_in_file)))

if warnings:
    print("Results imported with warning(s): " + " ".join(warnings))
    sys.exit(-1)
else:
    print("Results imported successfully for {} samples.".format(len(outputs)))


