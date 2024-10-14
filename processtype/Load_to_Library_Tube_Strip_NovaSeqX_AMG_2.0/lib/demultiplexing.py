# Function for getting the demultiplexing of artifacts
import logging
from genologics.lims import *

def get_demux_artifact(lims, lane_artifact):
    """Get the demultiplexed sample information from a pool artifact, from the demux API endpoint.

    Returns a list of tuples with the demultiplexed components of the pool/lane artifact.
    [(sample, artifact, reagent_label), ...]
    """

    demux_uri = lane_artifact.stateless.uri + "/demux"
    logging.info(f"Fetching demux endpoint {demux_uri} for artifact {lane_artifact.name} well {lane_artifact.location[1]}.")
    demux = lims.get(demux_uri)
    # Get all artifacts that are under a <demux> element (.// matches all children at any level). These may be partially
    # demultiplexed artifacts that have their own <demux> inside them. In that case, we will skip them and process only
    # fully demultiplexed, leaf-node artifacts.
    artifacts = demux.findall(".//demux/artifacts/artifact")
    if len(artifacts) == 0:
        logging.info(f"This lane has no <artifacts>, looks like a lane with a single sample. Will check if it has an index.")
        # If there is only one sample, we will get a single <artifact> element in the demux endpoint
        # which is the same as the lane_artifact we queried for demux
        art_check = demux.find('artifact')
        if (art_check is not None) and art_check.attrib['uri'] == lane_artifact.stateless.uri:
            num_labels = len(lane_artifact.reagent_labels)
            assert len(lane_artifact.samples) == 1, f"Non-pool artifact {lane_artifact.name} has {len(lane_artifact.samples)} samples, expected one sample."
            if num_labels == 1:
                # This single sample has an index
                logging.info(f"The lane artifact has a single reagent label.")
                return [(lane_artifact.samples[0], lane_artifact, next(iter(lane_artifact.reagent_labels)))]
            elif num_labels == 0:
                # The sample does not have an index
                logging.info(f"The lane artifact does not have an index.")
                return [(lane_artifact.samples[0], lane_artifact, None)]
            else:
                raise RuntimeError("Artifact {lane_artifact} has multiple reagent labels, but is not demultiplexed.")
        else:
            raise RuntimeError(f"Inconsistent result from API for unpooled artifact {lane_artifact.name} - demux endpoint artifact mismatch.")

    result_list = []
    for artifact in artifacts:
        if artifact.find('demux') is not None:
            continue # Skip partially demultiplexed artifact
        demux_artifact_name = artifact.attrib['name']
        demux_artifact = Artifact(lims, uri=artifact.attrib['uri'])

        # There should always be a sample associated with the artifact
        sample_elements = artifact.findall("samples/sample")
        if len(sample_elements) != 1:
            raise RuntimeError(f"Unexpected demux entry for lane {lane_artifact.name}: expected a single sample for "
                    f"artifact {demux_artifact_name} but found {len(sample_elements)}. Demux URI: {demux_uri}")
        sample = Sample(lims, uri=sample_elements[0].attrib['uri'])
        # Get the index name
        reagent_label_elements = artifact.findall("reagent-labels/reagent-label")
        if len(reagent_label_elements) == 0:
            reagent_label = None
        elif len(reagent_label_elements) == 1:
            reagent_label = reagent_label_elements[0].attrib['name']
        else:
            raise RuntimeError(f"There are multiple reagent labels in {demux_artifact_name}, in pool {lane_artifact.name}.")

        logging.info(f"Found artifact {demux_artifact_name}, sample {sample.name}, reagent label {reagent_label}.")
        result_list.append((sample, demux_artifact, reagent_label))
    return result_list
