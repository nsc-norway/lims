#!/bin/env python

#------------------------------#
# Conveyor
# NSC data processing manager
#------------------------------#

# This script monitors the LIMS via the REST API and starts programs.
# It only triggers scripts (emulates button presses) using the API to
# manage the processing status. 

import logging
import re
import sys
import time
import requests

# scilife genologics library
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
try:
    lims.check_version()
except requests.exceptions.ConnectionError:
    # Don't spam with errors if we can't reach LIMS
    sys.exit(0)

# Local copies of variables from the pipeline config package
TAG="prod"
DEMULTIPLEXING_QC_PROCESS = "Demultiplexing and QC NSC 2.0" 
SEQ_PROCESSES=[
                ('hiseqx', 'Illumina Sequencing (HiSeq X) 1.0'),
                ('hiseqx', 'AUTOMATED - Sequence'),
                ('hiseq4k', 'Illumina Sequencing (HiSeq 3000/4000) 1.0'),
                ('hiseq', 'Illumina Sequencing (Illumina SBS) 5.0'),
                ('nextseq', 'NextSeq Run (NextSeq) 1.0'),
                ('miseq', 'MiSeq Run (MiSeq) 5.0')
            ]

JOB_STATE_CODE_UDF = "Job state code"
CURRENT_JOB_UDF = "Current job"

def get_sequencing_process(process):
    """Copied from utitilies (pipeline repo)."""

    # Each entry in input_output_maps is an input/output specification with a single
    # input and any number of outputs. This gets the first input.
    first_io = process.input_output_maps[0]
    first_in_artifact = first_io[0]['uri']

    processes = process.lims.get_processes(inputartifactlimsid=first_in_artifact.id)
    seq_processes = [proc for proc in processes if proc.type_name in [p[1] for p in SEQ_PROCESSES]]
    # Use the last sequencing process. In case of crashed runs, this will be the right one.
    try:
        return seq_processes[-1]
    except IndexError:
        return None


def is_sequencing_finished(process):
    seq_process = get_sequencing_process(process)
    if not seq_process:
        logging.warning("Cannot detect the sequencing process, returning as if it's not completed")
        return False
    try:
        if seq_process.udf.get('Run Status') == "RunCompleted": # SeqLab
            return True
        if seq_process.udf['Finish Date'] and seq_process.udf['Read 1 Cycles']:
            match = re.match(r"Cycle (\d+) of (\d+)", seq_process.udf['Status'])
            if match:
                return match.group(1) == match.group(2)
    except KeyError:
        return False


def start_programs():
    processes = lims.get_processes(type=DEMULTIPLEXING_QC_PROCESS, udf={'Monitor': True})

    if not processes:
        logging.debug("No processes found")
        return

    for process in processes:
        logging.debug("Checking process " + process.id + "...")

        # Have to always check the Step, to see if it is closed, and if so
        # remove the Monitor flag. This is also done by the overview page 
        # (monitor/main.py), but we can't rely on that, since that may not be
        # used.
        step = Step(lims, id=process.id)
        if step.current_state.upper() == "COMPLETED":
            process.get()
            process.udf['Monitor'] = False
            process.put()
            logging.debug("Step " + process.id + " is completed, cleared Monitor flag")
            continue


        # Checks related to the UDF-based status tracking
        try:
            state = process.udf[JOB_STATE_CODE_UDF]
        except KeyError:
            state = None
        if state == "COMPLETED":
            previous_program = process.udf[CURRENT_JOB_UDF]
        elif state == None:
            previous_program = None
        else:
            logging.debug("Have to wait because program is in state " + str(state))
            continue # skip to next if state is not "COMPLETED" or None


        # Get the next program, based on UDF checkboxes
        auto_udf_match = [
                re.match(r"Auto ([\d-]+\..*)", udfname)
                for udfname, udfvalue in process.udf.items()
                if udfvalue
                ]
        auto_udf_name = sorted(m.group(1) for m in auto_udf_match if m)
        try:
            next_program = next(
                    button_name for button_name in auto_udf_name
                    if button_name > previous_program
                    )

        except StopIteration:
            logging.debug("Couldn't find the next checkbox after " + str(previous_program)
                    + ". Checking if step should be closed...")
            
            if process.udf.get('Close when finished'):
                seq_proc = get_sequencing_process(process)
                if not seq_proc or Step(lims, id=seq_proc.id).current_state.upper() == "COMPLETED":
                    logging.debug("Yes, will finish if no program is running.")
                    next_program = None
                else:
                    logging.debug("Waiting until the sequening step is closed.")
                    continue
            else:
                logging.debug("No, that was not requested.")
                continue


        # Check if sequencing is complete, if no program has been run
        if previous_program == None:
            logging.debug("Checking if sequencing is finished...")
            if not is_sequencing_finished(process):
                logging.debug("Wasn't.")
                continue

        logging.debug("Sequencing is finished, checking if we can start some jobs")

        # Check the native Clarity program status
        if step.program_status == None or step.program_status.status == "OK":

            # Now ready to start the program (push the button)
            if next_program:
                try:
                    button = next(
                            program 
                            for program in step.available_programs
                            if program.name == next_program
                            )

                    logging.debug("Triggering " + next_program)
                    button.trigger()

                except StopIteration:
                    logging.debug("Couldn't find the button for " + next_program)
            else: # Finish the step instead (if the Close.. checkbox is the next one)
                logging.debug("Finishing process " + process.id)
                for na in step.actions.next_actions:
                    na['action'] = 'complete'
                step.actions.put()
                fail = False
                while not fail and step.current_state.upper() != "COMPLETED":
                    logging.debug("Advancing the step...")
                    step.advance()
                    step.program_status.get(force=True)
                    while not fail and step.program_status.status != "OK":
                        logging.debug("A script is running (state: " + step.program_status.status + ")...")
                        if step.program_status not in ['QUEUED', 'RUNNING']:
                            fail = True
                        time.sleep(1)
                        step.program_status.get(force=True)
                    step.get(force=True)
                logging.debug("Completed " + process.id + ".")

        else:
            if step.program_status.status in ["RUNNING", "QUEUED"]:
                logging.debug("A program is executing, skipping this process")
            else:
                logging.debug("There's a program in state " + 
                        step.program_status.status + ", requires manual action")


if __name__ == "__main__":
    if TAG == "dev":
        logging.basicConfig(level=logging.DEBUG)
    logging.debug("auto.py Workflow management script")
    start_programs()


