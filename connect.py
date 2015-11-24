# Simple script to avoid some typing
# use: python -i connect.py
# To get an interactive session with lims.
from genologics.lims import *
from genologics import config

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

