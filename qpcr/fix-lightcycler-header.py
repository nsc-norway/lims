import sys
from genologics.lims import *
from genologics import config

def main(artifact_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    artifact = Artifact(lims, id=artifact_id)
    if len(artifact.files) == 0:
        print("ERROR: qPCR result file is missing.")
        sys.exit(1)

    file_object = artifact.files[0]
    file_data = file_object.download()

    lines = file_data.decode('utf-8').splitlines()
    lines[0] = lines[0].replace(" ", "\t")
    file_object.upload("\r\n".join(lines).encode('utf-8'))

    print("LightCycler Header Fixed Successfully")

main(*sys.argv[1:])

