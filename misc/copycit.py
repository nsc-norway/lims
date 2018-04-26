from genologics.lims import *
from genologics import config
import sys

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

old_kit = lims.get_reagent_kits(name=sys.argv[1])[0]
new_kit_data = {
        'name': sys.argv[2]
        }
for attr in ['supplier', 'website', 'catalogue_number', 'archived']:
    new_kit_data[attr] = getattr(old_kit, attr)

ReagentKit.create(lims, **new_kit_data)

