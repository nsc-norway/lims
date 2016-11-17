from flask import Flask, request, Response, jsonify, redirect
from genologics.lims import *
from genologics import config
import re
import requests
import itertools
import datetime
import threading
import yaml

# Back-end JSON REST service for reagent registration

# Edit the file kits.yml to set the kits.

# The previous version of this program used only the LIMS to get a
# list of kits, and matched the REF code to the catalogue number. While 
# that is a cleaner solution, it also had to know if the lots had to be
# automatically named based on the date, and it used to search for lots
# with a specific pattern. 
# To look at the version, see commit 898a94423d8cb367e60b630165a692b11df1c171

app = Flask(__name__)
lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

kit_list = yaml.load(open("kits.yml").read())
kits = dict((str(e['ref']), e) for e in kit_list)
lims_kits = {}

class KitDoesNotExistError(ValueError):
    pass

def get_date_string():
    seq_number_date = datetime.date.today()
    return seq_number_date.strftime("%y%m%d")

def get_lims_kit(name):
    if not lims_kits.has_key(name):
        try:
            lims_kits[name] = lims.get_reagent_kits(name=name)[0]
        except IndexError:
            raise KitDoesNotExistError("Kit " + str(name) + " does not exist in LIMS")
    return lims_kits[name]

@app.route('/kits/<ref>')
def get_kit(ref):
    try:
        kit = kits[ref]
        return jsonify({
                "name": kit['name'],
                "requestLotName": kit['hasUniqueId'],
                "found": True,
                "ref": kit['ref']
                })
    except KeyError, e:
        return ("Kit not found", 404)

def get_next_seq_number(kitname, lotcode):
    for i in itertools.count(1):
        name = "{0}-{1}-#{2}".format(get_date_string(), lotcode, i)
        lots = lims.get_reagent_lots(kitname=kitname, name=name)
        if not lots:
            return i

def get_next_name(kit):
    if kit['hasUniqueId']:
        return ""
    else:
        seq_number = get_next_seq_number(kit['name'], kit['lotcode'])
        return "{0}-{1}-#{2}".format(get_date_string(), kit['lotcode'], seq_number)

@app.route('/lots/<ref>/<lotnumber>', methods=['GET'])
def get_lot(ref, lotnumber):
    """Get information about lots with the requested
    lot number. There may be multiple lots in the system
    with the same lot number, if they have different lot
    names. This method returns the expiry date if available."""

    try:
        kit = kits[ref]
    except KeyError:
        return ("Kit not found", 404)
    lots = lims.get_reagent_lots(kitname=kit['name'], number=lotnumber)
    if lots:
        lot = next(iter(lots))
        return jsonify({
		"expiryDate": lot.expiry_date,
		"assignedUniqueId": get_next_name(kit),
		"known": True,
		"lotnumber": lotnumber,
		"ref": ref
    	})
    else:
        return jsonify({
		"expiryDate": None,
		"assignedUniqueId": get_next_name(kit),
		"known": False,
		"lotnumber": lotnumber,
		"ref": ref
    	})

@app.route('/lots/<ref>/<lotnumber>', methods=['POST'])
def create_lot(ref, lotnumber):
    try:
        kit = kits[ref]
    except KeyError:
        return ("Kit not found", 404)
    data = request.json
    try:
        if lotnumber != data['lotnumber']:
            return ("Lot number does not match URI", 400)
        try:
            unique_id = data.get('assignedUniqueId')
            if not unique_id:
                if not kit.get('hasUniqueId'):
                    unique_id = get_next_name(kit)
                else:
                    unique_id = "{0}-{1}".format(data['uniqueId'], kit['lotcode'])
            lot = lims.create_lot(
                get_lims_kit(kit['name']),
                unique_id,
                lotnumber,
                data['expiryDate'].replace("/", "-"),
                status='ACTIVE'
            )
        except requests.HTTPError, e:
            if 'Duplicate lot' in e.message:
                return ("Lot with same name and number already exists", 400)
            else:
                return ("There was a protocol error between the backend and the LIMS server.", 500)
        except KitDoesNotExistError, e:
            return (str(e), 500)
    except KeyError, e:
        return ("Missing required field " + str(e), 400)

    return jsonify({
        "expiryDate": lot.expiry_date,
        "uniqueId": lot.name,
        "assignedUniqueId": lot.name,
        "known": True,
        "lotnumber": lotnumber,
        "ref": ref
        })

@app.route('/')
def redir_index():
    return redirect("app/index.html")

if __name__ == '__main__':
    app.debug=True
    app.run(host="0.0.0.0", port=5001)

