import pandas as pd
from genologics.lims import *
from genologics import config
import logging
import sys
import os

NAME_RACK_TUBE = "RackTube"
NAME_NSC = "NSC"

def main(process_id, robot_file, worksheet_file):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    process = Process(lims, id=process_id)
    logging.info(f"Generating robot file for process {process.id}")
    process.get()

    logging.debug("Pre-caching input and output artifacts")
    lims.get_batch(xput['uri'] for i, o in process.input_output_maps for xput in [i, o])

    outputs = set(o['uri'] for i, o in process.input_output_maps if o['output-type'] == 'Analyte')

    # Check single output plate
    output_location_id = next(iter(outputs)).location[0].id
    assert all(o.location[0].id == output_location_id for o in outputs), \
            "Error: There can only be one output container."

    # The following lists will contain the output table
    common_rows = []
    worksheet_rows = []
    robot_rows = []

    source_position_calculator = SourcePositionCalculator()

    # PhiX stock concentration for use in manual and robotic blending / spiking
    phix_molarity = 2 # nM
    # PhiX is always 4.8 microlitres per lane for the robot: giving 1 % PhiX from 2 nM conc. PhiX.
    phix_volume_simple = 4.8
    # This is the final total volume after also a4dding other reagents. This is only used to translate
    # to 'Input Conc. (pM)', which is specified in reference to this total volume.
    final_total_volume = 281.6 # uL

    # Apply a scaling factor to all volumes on the robot
    robot_volume_scaling = 1.1

    for output in outputs:
        logging.info(f"Processing output {output.name}")

        inputs = [i['uri'] for i, o in process.input_output_maps if o['uri'] == output]

        # Get required fields for calculation
        try:
            phix_percent = output.udf['PhiX %']
            target_input_molarity = output.udf['Input Conc. (pM)']
        except KeyError as e:
            logging.error(f"Library {output.name} (for target well {output.location[1]}) is missing field {e}.")
            sys.exit(1)

        assert target_input_molarity >= 0.0, "Target input conc. should be a non-negative number."

        if phix_percent < 0.0 or phix_percent > 100.0:
            logging.error("PhiX should be between 0 and 100 %")
            sys.exit(1)

        if phix_percent < 1.0:
            logging.error("Cannot use less than 1 % PhiX. The robot will add 1 % PhiX.")
            sys.exit(1)
            # We may want to use 0 % PhiX and completely manual dilution.
            # The log warning will not be visible.
            #phix_percent = 1.0
            #phix_fraction = 0.01

        phix_fraction = phix_percent / 100

        # Sort into spike-in and non-spike-in inputs
        non_spikein_inputs = [i for i in inputs if not i.udf.get('Spike-in %')]
        if len(non_spikein_inputs) != 1:
            logging.error(f"There must be exactly one main (non-spike-in) library/pool per target well. Found {len(non_spikein_inputs)} main libraries/pools in location {output.location[1]}.")
            sys.exit(1)

        spikein_inputs = [i for i in inputs if i.udf.get('Spike-in %')]

        # Compute total spike-in percentage (generally in case of mulitple spike-ins that are specified as
        # percentages of the total concentration / quantity)
        total_spike_fraction = sum(i.udf['Spike-in %'] for i in spikein_inputs) / 100.0
        # Main library - fraction of the output bulk
        nonspike_fraction = (1.0 - total_spike_fraction - phix_fraction)

        logging.info(f"There is one main library and {len(spikein_inputs)} spike-ins. Total spike-in amount {total_spike_fraction*100} %.")

        # Required nanomoles of the output bulk
        total_bulk_nmoles = (target_input_molarity / 1000) * final_total_volume
        logging.info(f"The total amount of DNA should be {total_bulk_nmoles} nanomoles.")

        # Loop over inputs to calculate volumes and populate most of the table rows.
        sum_robot_library_volume = 0 # aggregate library volumes across spike-ins (microlitres)
        set_rsb_in_main_library_row = None # Keep a reference to the main library robot row, in which to set the RSB
        for input in non_spikein_inputs + spikein_inputs:
            logging.info(f"Getting input properties and calculations for {input.name}.")

            # The common cells should be included in both output files
            common_row = {}
            # Robot and worksheet cells are separate because they may have the same columns with different values(!)
            # The worksheet contains calculations for manual dilution
            worksheet_row = {}
            # Robot: Source Plate,Source Position,Output Plate Position,Library Name,Library Volume,RSB Volume
            robot_row = {}

            common_row['Library Name'] = input.name
            common_row['Source Plate'], common_row['Source Position'] = source_position_calculator.compute_source(input)
            common_row['OutPut Plate Position'] = output.location[1].replace(":", "")
            
            is_spike_in = bool(input.udf.get('Spike-in %'))
            actual_library_molarity = get_library_molarity(input, is_spike_in)

            # Add informative columns in worksheet
            worksheet_row['Sample Conc. (nM)'] = actual_library_molarity
            worksheet_row['Input Conc. (pM)'] = target_input_molarity
            worksheet_row['PhiX %'] = phix_percent

            # Get library quantity
            if is_spike_in:
                this_library_quantity = total_bulk_nmoles * (input.udf['Spike-in %'] / 100)
                robot_row['RSB Volume'] = 0.0
                logging.info(f"Required DNA quantity for spike-in library {input.name} is {this_library_quantity} nanomoles.")
            else:
                this_library_quantity = total_bulk_nmoles * nonspike_fraction
                set_rsb_in_main_library_row = robot_row
                logging.info(f"Required DNA quantity for main library {input.name} is {this_library_quantity} nanomoles.")

            # Calculate sample volume. The logic is different for robot file and worksheet, due to how
            # the lab workflow is done. The robot will always add 1% PhiX. The manual workflow is designed
            # to handle cases when the PhiX concentration is greater than 1 %.
            if phix_percent == 1.0 or is_spike_in:
                logging.info(f"Library {input.name} has 1 % PhiX and/or is a spike-in, setting columns to zero in worksheet.")
                worksheet_row['Library Volume'] = 0.0
                worksheet_row['RSB Volume'] = 0.0
                worksheet_row[f'PhiX {phix_molarity}nM Volume'] = 0.0
                library_molarity_robot = actual_library_molarity
                library_volume_robot = this_library_quantity / actual_library_molarity
            else:
                logging.info(f"Library {input.name} requires {phix_percent} % PhiX - computing manual dilution.")

                # The library and PhiX will be diluted to a predefined intermeditate molarity (1.5 nM)
                # in the manual step.
                # It's not possible to do the final dilution directly to target_input_molarity pM manually, because it could
                # produce a too large volume for the robot to pipette.
                # The robot uses the manually diluted PhiX blend as input, instead of the actual library.
                library_molarity_robot = 1.5 # nM Note this is the molarity of the PhiX + library blend!

                # First compute the required amount of mix to be used by the robot, at 1.5 nM.
                phix_fraction_manual = phix_fraction - 0.01
                library_volume_robot = ((total_bulk_nmoles * phix_fraction_manual) + this_library_quantity) / library_molarity_robot

                # We want to some excess volume, but at the 1.5 nM concentration. The robot won't use this excess.
                required_mix_volume = 10 + library_volume_robot * robot_volume_scaling # uL

                # Compute the total DNA quantity required, in nanomoles
                required_dna_quantity = required_mix_volume * library_molarity_robot # nmol
                
                phix_quantity_manual = required_dna_quantity * phix_fraction_manual
                library_quantity_manual = required_dna_quantity * (1.0 - phix_fraction_manual)

                # Compute volumes of PhiX and library
                phix_volume_manual = phix_quantity_manual / phix_molarity # nmol / (nmol/uL) = uL
                worksheet_row[f'PhiX {phix_molarity}nM Volume'] = phix_volume_manual
                
                library_volume_manual = library_quantity_manual / actual_library_molarity # uL
                worksheet_row['Library Volume'] = library_volume_manual

                # Buffer is what is remaining to fill the volume
                worksheet_row['RSB Volume'] = required_mix_volume - library_volume_manual - phix_volume_manual
            
            sum_robot_library_volume += library_volume_robot
            robot_row['Library Volume'] = library_volume_robot * robot_volume_scaling

            common_rows.append(common_row)
            robot_rows.append(robot_row)
            worksheet_rows.append(worksheet_row)

        # Compute RSB (robot) - only available after all library volumes are calculated
        # Total volume that should be present in the library tube strip after dilution and adding PhiX:
        output_volume = 57.6 # uL
        # RSB
        rsb_volume_robot = output_volume - phix_volume_simple - sum_robot_library_volume
        # Go back and set it in the row that was appended in the loop above
        set_rsb_in_main_library_row['RSB Volume'] = rsb_volume_robot * robot_volume_scaling
        logging.info(f"Processed all inputs for output position {output.location[1]} and set Robot RSB {rsb_volume_robot} uL.")

    logging.info(f"Sorting the rows.")
    # The spec is to sort by type (plate / nsc / racktube) and by input container (plate). The
    # function also sorts by output well ID, so the order is predictable.
    all_three = [(c, r, w) for c, r, w in zip(common_rows, robot_rows, worksheet_rows)]
    all_three_sorted = sorted(all_three, key=output_row_ordering)
    common_rows, robot_rows, worksheet_rows = zip(*all_three_sorted)

    logging.info(f"Processed all input-output pairs. Will generate robot file.")

    # Write robot file
    pd.DataFrame(
            [dict(**c, **r) for c, r in zip(common_rows, robot_rows)],
            columns = ['Source Plate', 'Source Position', 'OutPut Plate Position', 'Library Name', 'Library Volume', 'RSB Volume']
            ).to_csv(robot_file, index=False, float_format = "%.2f")

    logging.info(f"Generating worksheet file.")

    # Write worksheet file
    pd.DataFrame(
            [dict(**c, **w) for c, w in zip(common_rows, worksheet_rows)],
            columns = ['Source Plate', 'Source Position', 'OutPut Plate Position', 'Library Name', 'Sample Conc. (nM)',
                'Input Conc. (pM)', 'PhiX %',
                'Library Volume', 'RSB Volume', f'PhiX {phix_molarity}nM Volume']
            ).to_csv(worksheet_file, index=False, float_format = "%.2f")


def output_row_ordering(common_robot_worksheet):
    common, robot, worksheet = common_robot_worksheet
    output_position = common['OutPut Plate Position']
    well_index = (int(output_position[1:]), output_position[:1])
    if common['Source Plate'] == NAME_RACK_TUBE:
        section_index = 2
    elif common['Source Plate'] == NAME_NSC:
        section_index = 1
    else:
        section_index = 0
    return section_index, common['Source Plate'], well_index


class SourcePositionCalculator:
    def __init__(self):
        self.rack_tube_input_counter = 0
        self.nsc_tube_input_counter = 0
        self.known_unique_input_tubes = {}
        self.nsc_tube_position_sequence = [c + r for r in "12" for c in "ABCDEFGH"]
        self.rack_tube_position_sequence = [str(i) for i in range(1, 33)]

    def compute_source(self, input):
        if input.location[0].type.name == "Tube":
            try:
                project_type = input.samples[0].project.udf['Project type']
            except:
                project_type = None

            container_name = input.location[0].name
            if project_type in ["Diagnostics", "Microbiology"]:
                # Use RackTube for MIK spike-in
                source_plate = NAME_RACK_TUBE
                tube_id_name = container_name + "." + input.id

                if tube_id_name in self.known_unique_input_tubes:
                    source_position = self.known_unique_input_tubes[tube_id_name]
                else:
                    new_tube_position = self.rack_tube_position_sequence[self.rack_tube_input_counter]
                    self.rack_tube_input_counter += 1
                    source_position = new_tube_position
                    self.known_unique_input_tubes[tube_id_name] = new_tube_position
            elif project_type in ["Sensitive", "Non-sensitive"]:
                source_plate = NAME_NSC
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

                if tube_id_name in self.known_unique_input_tubes:
                    source_position = self.known_unique_input_tubes[tube_id_name]
                else:
                    new_tube_position = self.nsc_tube_position_sequence[self.nsc_tube_input_counter]
                    self.nsc_tube_input_counter += 1
                    source_position = new_tube_position
                    self.known_unique_input_tubes[tube_id_name] = new_tube_position
            else:
                logging.error(f"Don't know correct tube rack for project type {project_type}.")
                sys.exit(1)
        else:
            source_plate = input.location[0].name
            # The LIMS position is separated by colon, we will REMOVE THE COLON
            source_position = input.location[1].replace(":", "")
        return source_plate, source_position


def get_library_molarity(input, is_spike_in):
    # Get the sample molarity from one of these fields
    spike_in_molarity = input.udf.get('Spike-in final molarity (nM)')
    molarity = input.udf.get('Molarity')
    molarity_nm = input.udf.get('Molarity (nM)')
    normalized_conc = input.udf.get('Normalized conc. (nM)')
    logging.info(f"Input {input.name} has 'Spike-in final molarity (nM)': {spike_in_molarity}, 'Molarity': {molarity}, 'Molarity (nM)': {molarity_nm}, 'Normalized conc. (nM)': {normalized_conc}.")
    if is_spike_in and (spike_in_molarity is not None):
        # Spike-in molarity field trumps everything
        library_conc = spike_in_molarity 
    else:
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
            logging.error(f"No molarity fields are available for {input.name} (input ID {input.id}).")
            sys.exit(1)

    logging.info(f"Using: {library_conc}.")
    return library_conc


if __name__ == "__main__":

    if len(sys.argv) < 5:
        print(f"Usage: {sys.argv[0]} PROCESS_ID ROBOT_FILE_NAME WORKSHEET_FILE_NAME LOG_FILE_NAME")
        sys.exit(0)

    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(level=log_level, filename=sys.argv[4])

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel('WARNING')
    logging.getLogger('').addHandler(console_handler)


    main(sys.argv[1], sys.argv[2], sys.argv[3])
