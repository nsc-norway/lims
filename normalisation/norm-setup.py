import sys
import csv
import StringIO
from genologics.lims import *
from genologics import config

# Setup script for normalisation:
# - Copies UDFs from inputs to outputs
# - Sets default normalised concentration and input volume on each output

# use:
# python norm-setup.py PROCESS-ID INPUT-VOL NORM-CONC
# 
# PROCESS-ID: LIMS process ID
# INPUT-VOL:  Volume to take from inputs (will set lower if volume UDF of input is less)
# NORM-CONC:  Desired normalised concentration (set as is, not checked)

def main(process_id, input_vol, norm_conc):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    
    
    

main(sys.argv[1], sys.argv[2], sys.argv[3])

