from flask import Flask, request, Response, jsonify
from genologics.lims import *
from genologics import config
import re
import itertools
import datetime


# Back-end JSON REST service for reagent registration

app = Flask(__name__)
lims = None

cat_kit = {}

# Kit naming:
# - Default is to request full kit names. Used for unknown,
#   and RGT numbers. No entry in this dict.
# - For date+sequential naming: values are ["PREFIX", day_index]
seq_number_date = datetime.date.today()
kit_naming = {}

def get_next_seq_number(kitname, lotcode):
    for i in itertools.count():
        name = "{0}-{1}{2}".format(seq_number_date, lotcode, i)
        lot = lims.get_reagent_lots(kitname=kitname, name=name)
        if not lot:
            return i

def get_date_string():
    return datetime.date.today().strftime("%y%m%d")

@app.route('/refresh', methods=['POST'])
def refresh():
    global lims

    # Clear client cache
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    seq_number_date = get_date_string()

    print "Initializing (kits)..."
    kits = lims.get_reagent_kits()
    for kit in kits:
        if kit.catalogue_number:
            for cat in kit.catalogue_number.split(","):
                cat_kit[cat.strip()] = kit
    print "Initializing (lots)..."
    for kit in cat_kit.values():
        lots = lims.get_reagent_lots(kitname=kit.name)
        for i, lot in enumerate(lots):
            if lot.name.startswith("RGT"):
                kit_mode[kit] = None
                break
            else:
                m = re.match(r"\d{6}-([A-Z]+)\d+$", lot.name)
                if m:
                    code = m.group(1)
                    next_seq_number = get_next_seq_number(kit.name, code)
                    kit_naming[kit] = [code, next_seq_number]
                    break

    print "Done."

class Kit(object):
    def __init__(self, name, requestLotName, ref):
        self.name = name
        self.requestLotName = requestLotName
        self.found = True
        self.ref = ref

@app.route('/kits/<ref>')
def get_kit(ref):
    try:
        kit = cat_kit[ref]
        kit_obj = Kit("Hello", True, ref)
        return jsonify(kit_obj)
    except KeyError:
        return ("Kit not found", 404, {})

@app.route('/lots/<lotnumber>', methods=['GET'])
def get_lot(lotnumber):
    """Get information about lots with the requested
    lot number. There may be multiple lots in the system
    with the same lot number, if they have different lot
    names. This method returns the next sequential lot
    name, if applicable, and the expiry date if available."""
    pass

@app.route('/lots/<lotnumber>', methods=['POST'])
def create_lot(lotnumber):
    pass

refresh()

if __name__ == '__main__':
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
