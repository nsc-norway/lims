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
known_unique_input_tubes = {}
tube_position_sequence = [c + r for r in "12" for c in "ABCDEFGH"]

logging.debug("Pre-caching input and output artifacts")
lims.get_batch(xput['uri'] for i, o in process.input_output_maps for xput in [i, o])

# Extract the relevant inputs and outputs. Sort by destination well
# position in column order. Spike-in pools are sorted after the
# main pools.
def get_column_sort_key(artifact):
    row, column =  artifact.location[1].split(":")
    return int(column), row, artifact.id

position_sorted_output = sorted([
        o['uri'] for i, o in process.input_output_maps if o['output-type'] == 'Analyte'
    ], key=get_column_sort_key)


# Check single output plate
output_location_id = position_sorted_output[0].location[0].id
assert all(o.location[0].id == output_location_id for o in position_sorted_output), \
        "Error: There can only be one output container."

# Will contain the output table
common_rows = []
worksheet_rows = []
robot_rows = []
for output in position_sorted_output:

    inputs = [i['uri'] for i, o in process.input_output_maps if o['uri'] == output]
    library_volume_sum = 0

    #TODO
for input, output in position_sorted_input_output:
    logging.info(f"Processing input {input.name}")

    common_row = {}
    # Robot and worksheet rows are separate because they may have the same columns with different values(!)
    # The worksheet contains calculations 
    worksheet_row = {}
    # Robot: Source Plate,Source Position,Output Plate Position,Library Name,Library Volume,RSB Volume
    robot_row = {}

    if input.location[0].type.name == "Tube":
        common_row['Source Plate'] = tube_input_container_name
        container_name = input.location[0].name
        cn_parts = container_name.rsplit("_", maxsplit=1)
        if len(cn_parts) > 1 and cn_parts[-1].isdigit():
            # Remove underscore and numeric suffix for tubes that have been duplicated on the
            # Queue for sequencing NSC step, because they should be run on multiple lanes.
            # These will have the name as original plate position and then _01, _02, etc. They
            # should be treated as a single tube because that's what they are.
            tube_id_name = cn_parts[0] + "^" + input.name
        else:
            # The input is now identified by container name and ID. This may work if the
            # step is configured with "variable number of outputs" and the library is
            # duplicated when entering this step.
            tube_id_name = container_name + "." + input.id
        if tube_id_name in known_unique_input_tubes: 
            common_row['Source Position'] = known_unique_input_tubes[tube_id_name]
        else:
            new_tube_position = tube_position_sequence[tube_input_counter] 
            tube_input_counter += 1
            common_row['Source Position'] = new_tube_position
            known_unique_input_tubes[tube_id_name] = new_tube_position
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
    logging.info(f"Input {input.name} has 'Molarity': {molarity}, 'Molarity (nM)': {molarity_nm}, 'Normalized conc. (nM)': {normalized_conc}.")
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

    logging.info(f"Using: {library_conc}.")
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
    # PhiX stock concentration for use in manual and robotic blending / spiking
    phix_conc = 2 # nM
    # This is the total volume that should be present in the library tube strip after dilution and
    # adding PhiX.
    output_volume = 57.6 # uL
    # This is the final total volume after also adding other reagents. This is only used to translate
    # to 'Input Conc. (pM)', which is specified in reference to this total volume.
    final_total_volume = 281.6 # uL

    # Calculate sample volume. The logic is different for robot file and worksheet, due to how
    # the lab workflow is done. The robot will always add 1% PhiX. The manual workflow is designed
    # to handle cases when the PhiX concentration is greater than 1 %. If PhiX is 1 %, the lab
    # sheet should just have zeros for that library.
    if phix_percent == 1.0:
        library_conc_robot = library_conc
    else:
        # The library and PhiX will be diluted to a predefined intermeditate molarity (1.5 nM)
        # in the manual step.
        # It can't do the final dilution to target_input_conc pM manually, because there would be too
        # large volume for the robot to pipette.
        # The robot then uses this as input, instead of the actual library conc.
        library_conc_robot = 1.5 # nM

    # Calculate dilution of library, or PhiX + library blend from manual step, on the robot
    library_volume_robot = (target_input_conc/1000) * final_total_volume / library_conc_robot
    # PhiX volume is always 4.8 for 1 % PhiX
    phix_volume_simple = 4.8
    # For robot file
    rsb_volume_robot = output_volume - library_volume_robot - phix_volume_simple

    if phix_percent == 1.0:
        logging.info(f"Library {input.name} has 1% PhiX, setting columns to zero in worksheet.")
        worksheet_row['Library Volume'] = 0.0
        worksheet_row['RSB Volume'] = 0.0
        worksheet_row[f'PhiX {phix_conc}nM Volume'] = 0.0
    else:
        phix_fraction = (phix_percent - 1.0) / 100

        # This volume is always the same. Based on the predefined robot conc. plus some extra.
        required_mix_volume = 10 + library_volume_robot # uL
        logging.info(f"Library {input.name} requires {phix_percent} % PhiX - computing manual dilution to"
                        f" {library_conc_robot} nM in {required_mix_volume} uL.")

        # Compute the total DNA quantity required, in nanomoles
        required_dna_quantity = required_mix_volume * library_conc_robot # nmol
        
        phix_quantity = required_dna_quantity * phix_fraction
        library_quantity = required_dna_quantity * (1.0 - phix_fraction)

        # Compute volumes of PhiX and library
        phix_volume = phix_quantity / phix_conc # nmol / (nmol/uL) = uL
        worksheet_row[f'PhiX {phix_conc}nM Volume'] = phix_volume
        
        library_volume = library_quantity / library_conc # uL
        worksheet_row['Library Volume'] = library_volume

        # Buffer is what is remaining to fill the volume
        worksheet_row['RSB Volume'] = required_mix_volume - library_volume - phix_volume



    # Store computed values for the robot
    robot_row['Library Volume'] = library_volume_robot
    robot_row['RSB Volume'] = rsb_volume_robot
    
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

