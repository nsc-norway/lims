from flask import Flask, request, Response, jsonify, redirect
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
    for i in itertools.count(1):
        name = "{0}-{1}{2}".format(get_date_string(seq_number_date), lotcode, i)
        lots = lims.get_reagent_lots(kitname=kitname, name=name)
        if not lots:
            return i

def get_date_string(date):
    return date.strftime("%y%m%d")

@app.route('/refresh', methods=['POST'])
def refresh():
    global lims, seq_number_date

    # Clear client cache
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

    seq_number_date = datetime.date.today()

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
                kit_naming[kit] = None
                break
            else:
                m = re.match(r"\d{6}-([A-Z]+)\d+$", lot.name)
                if m:
                    code = m.group(1)
                    next_seq_number = get_next_seq_number(kit.name, code)
                    kit_naming[kit] = [code, next_seq_number]
                    break
        else:
            kit_naming[kit] = None

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
        return jsonify({
                "name": kit.name,
                "requestLotName": kit_naming[kit] is None,
                "found": True,
                "ref": ref
                })
    except KeyError:
        return ("Kit not found", 404)

def get_next_name(kit):
    global seq_number_date
    if seq_number_date != datetime.date.today():
        for value in kit_naming.values():
            if value:
                value[1] = 1
    seq_number_date = datetime.date.today()
    naming = kit_naming[kit]
    if naming:
        return "{0}-{1}{2}".format(get_date_string(seq_number_date), *naming)
    else:
        return ""

@app.route('/lots/<ref>/<lotnumber>', methods=['GET'])
def get_lot(ref, lotnumber):
    """Get information about lots with the requested
    lot number. There may be multiple lots in the system
    with the same lot number, if they have different lot
    names. This method returns the expiry date if available."""

    try:
        kit = cat_kit[ref]
    except KeyError:
        return ("Kit not found", 404)
    lots = lims.get_reagent_lots(kitname=kit.name, number=lotnumber)
    if lots:
        lot = next(iter(lots))
        return jsonify({
		"expiryDate": lot.expiry_date,
		"uid": get_next_name(kit),
		"known": True,
		"lotnumber": lotnumber,
		"ref": ref
    	})
    else:
        return jsonify({
		"expiryDate": None,
		"uid": get_next_name(kit),
		"known": False,
		"lotnumber": lotnumber,
		"ref": ref
    	})

@app.route('/lots/<ref>/<lotnumber>', methods=['POST'])
def create_lot(ref, lotnumber):
    try:
        kit = cat_kit[ref]
    except KeyError:
        return ("Kit not found", 404)
    data = request.json
    try:
        if lotnumber != data['lotnumber']:
            return ("Lot number does not match URI", 400)
        lot = lims.create_lot(
            kit,
            data['uid'],
            lotnumber,
            data['expiryDate'],
            status='ACTIVE'
        )
    except KeyError, e:
        return ("Missing required field " + str(e), 400)

    return jsonify({
        "expiryDate": lot.expiry_date,
        "uid": lot.name,
        "known": True,
        "lotnumber": lotnumber,
        "ref": ref
        })

@app.route('/')
def redir_index():
    return redirect("app/index.html")

refresh()

if __name__ == '__main__':
    app.debug=True
    app.run(host="0.0.0.0", port=5001)
