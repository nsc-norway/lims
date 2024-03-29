import pandas as pd
from genologics.lims import *
from genologics import config
import logging
import sys
import os

if len(sys.argv) < 5:
    print(f"Usage: {sys.argv[0]} PROCESS_ID ROBOT_FILE_NAME WORKSHEET_FILE_NAME LOG_FILE_NAME")
    sys.exit(0)

log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=log_level, filename=sys.argv[4])

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel('WARNING')
logging.getLogger('').addHandler(console_handler)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)


process = Process(lims, id=sys.argv[1])
logging.info(f"Generating robot file for process {process.id}")
process.get()


# Costants used for tube to plate conversion
tube_input_container_name = "NSC"
tube_input_counter = 0
tube_position_sequence = [c + r for r in "12" for c in "ABCDEFGH"]

# Extract the relevant inputs and outputs. Sort by destination well
# position in column order
def get_column_sort_key(artifact):
    row, column =  artifact.location[1].split(":")
    return int(column), row, artifact.id
position_sorted_input_output = sorted([
        (get_column_sort_key(o['uri']), i['uri'], o['uri'])
        for i, o in process.input_output_maps
        if o['output-type'] == 'Analyte' ])
logging.debug("Pre-caching input and output artifacts")
lims.get_batch(artifact for _, i, o in position_sorted_input_output for artifact in [i, o])

# Check columns
assert all(column in [1, 7] for (column, _, _), _, _ in position_sorted_input_output), \
        "Errror: Samples should only be placed in column 1 or 7."
# Check single output plate
output_location_id = position_sorted_input_output[0][2].location[0].id
assert all(o.location[0].id == output_location_id for _, _, o in position_sorted_input_output), \
        "Error: There can only be one output container."

# Will contain the output table
common_rows = []
worksheet_rows = []
robot_rows = []
for _, input, output in position_sorted_input_output:
    logging.info(f"Processing input {input.name}")

    common_row = {}
    # Robot and worksheet rows are separate because they may have the same columns with different values(!)
    # The worksheet contains calculations 
    worksheet_row = {}
    # Robot: Source Plate,Source Position,Output Plate Position,Library Name,Library Volume,RSB Volume
    robot_row = {}

    if input.location[0].type.name == "Tube":
        common_row['Source Plate'] = tube_input_container_name
        common_row['Source Position'] = tube_position_sequence[tube_input_counter]
        tube_input_counter += 1
    else:
        common_row['Source Plate'] = input.location[0].name
        # The LIMS position is separated by colon, we will REMOVE THE COLON
        common_row['Source Position'] = input.location[1].replace(":", "")
    common_row['OutPut Plate Position'] = output.location[1].replace(":", "")
    common_row['Library Name'] = input.name

    # Get the sample molarity from one of these fields
    molarity = input.udf.get('Molarity')
    molarity_nm = input.udf.get('Molarity (nM)')
    normalized_conc = input.udf.get('Normalized conc. (nM)')
    # If it has "Molarity" fields, it means a measurement is done on this artifact.
    # We falled back on Normalized Conc. (nM) if there is no measurement.
    if molarity is None:
        library_conc = molarity_nm
    else:
        if molarity_nm is not None:
            logging.error(f"Input {input.name} has both 'Molarity' and 'Molarity (nM)'. Don't know which one to use.")
            sys.exit(1)
        library_conc = molarity
    if library_conc is None:
        logging.info(f"There is no measured molarity on {input.name}, falling back to Normalized Conc. (nM)")
        library_conc = normalized_conc
    if library_conc is None:
        logging.error(f"No molarity fields are available for {input.name} (target well {output.location[1]} input ID {input.id}).")
        sys.exit(1)

    # Get required fields for calculation
    try:
        phix_percent = output.udf['PhiX %']
        target_input_conc = output.udf['Input Conc. (pM)']
    except KeyError as e:
        logging.error(f"Sample {input.name} (for target well {output.location[1]}) is missing field {e}.")
        sys.exit(1)
    assert phix_percent >= 0.0 and phix_percent <= 100.0, "PhiX should be between 0 and 100 %"
    assert target_input_conc >= 0.0, "Target input conc. should be a non-negative number."

    # Add informative columns in worksheet
    worksheet_row['Sample Conc. (nM)'] = library_conc
    worksheet_row['Input Conc. (pM)'] = target_input_conc
    worksheet_row['PhiX %'] = phix_percent

    # Define constants
    phix_conc = 2 # nM
    total_volume_constant = 56.7

    # Calculate sample volume. The logic is different for robot file and worksheet, due to how
    # the lab workflow is done. The robot will always add 1% PhiX. The manual workflow is designed
    # to handle cases when the PhiX concentration is different from 1 %. If PhiX is 1 %, the lab
    # sheet should just have zeros for that library.
    library_volume_simple = (target_input_conc/1000) * 281.6 / library_conc
    # PhiX volume is always 4.8 for 1 % PhiX
    phix_volume_simple = 4.8
    rsb_volume_simple = total_volume_constant - library_volume_simple - phix_volume_simple

    if phix_percent == 1.0:
        logging.info(f"Library {input.name} has 1% PhiX, setting columns to zero in worksheet.")
        worksheet_row['Library Volume'] = 0.0
        worksheet_row['RSB Volume'] = 0.0
        worksheet_row['PhiX 2nM Volume'] = 0.0
    else:
        phix_fraction = phix_percent / 100
        logging.info(f"Library {input.name} has {phix_percent} % PhiX - computing manual dilution.")
        logging.info(f"For the following automated dilution we need to input 1.1 x {total_volume_constant} uL of sample+phix+rsb mix.")

        required_total_volume = 1.1 * total_volume_constant # uL
        required_dna_quantity = 281.6 * target_input_conc / 1000 # nmol

        # Compute nanomoles of library and phix needed to produce the necessary DNA conc.
        required_library_quantity = required_dna_quantity * (1-phix_fraction)
        required_phix_quantity = required_dna_quantity * phix_fraction

        # Compute volume of ibrary and phix
        library_volume = required_library_quantity / library_conc # uL
        phix_volume = required_phix_quantity / phix_conc
        worksheet_row['Library Volume'] = library_volume
        worksheet_row[f'PhiX {phix_conc}nM Volume'] = phix_volume

        # Buffer is what is remaining to fill the volume
        worksheet_row['RSB Volume'] = required_total_volume - library_volume - phix_volume

        logging.info(f"Computed manual dilution, resetting volumes for robot")
        library_volume_simple = total_volume_constant
        rsb_volume_simple = 0.0

    # Store computed simple values for the robot. If the samples were diluted manually, the simple
    # volumes are adjusted to include only the sample and no rsb - the sample will already be at the
    # correct conc.
    # Add 10% extra volumes in robot.
    robot_row['Library Volume'] = 1.1 * library_volume_simple
    robot_row['RSB Volume'] = 1.1 * rsb_volume_simple
    
    common_rows.append(common_row)
    robot_rows.append(robot_row)
    worksheet_rows.append(worksheet_row)

logging.info(f"Processed all input-output pairs. Will generate robot file.")

# Write robot file
pd.DataFrame(
        [dict(**c, **r) for c, r in zip(common_rows, robot_rows)],
        columns = ['Source Plate', 'Source Position', 'OutPut Plate Position', 'Library Name', 'Library Volume', 'RSB Volume']
        ).to_csv(sys.argv[2], index=False, float_format = "%.2f")

logging.info(f"Generating worksheet file.")

# Write worksheet file
pd.DataFrame(
        [dict(**c, **w) for c, w in zip(common_rows, worksheet_rows)],
        columns = ['Source Plate', 'Source Position', 'OutPut Plate Position', 'Library Name', 'Sample Conc. (nM)',
            'Input Conc. (pM)', 'PhiX %',
            'Library Volume', 'RSB Volume', f'PhiX {phix_conc}nM Volume']
        ).to_csv(sys.argv[3], index=False, float_format = "%.2f")

