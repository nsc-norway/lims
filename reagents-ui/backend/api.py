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

# This service allows unauthenticated access to query kit types and lots,
# and to add new lots and edit existing lots. It uses the file kits.yml 
# to keep a mapping of "REF" numbers, printed on barcodes, to kit 
# information. Clients can also add entries to kits.yml via the API.

# This back-end service supports both the reagent scanning web application 
# (in the parent directory) and the webcam-based Java application in the
# reagent-scanning repo.

# The previous version of this program used only the LIMS to get a
# list of kits, and matched the REF code to the catalogue number. While 
# that is a cleaner solution, it also had to know if the lots had to be
# automatically named based on the date, and it used to search for lots
# with a specific pattern. 
# To look at the version, see commit 898a94423d8cb367e60b630165a692b11df1c171

app = Flask(__name__)

lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)

kits_file = "kits.yml"

# Hard coded name mapping for various "groups"
# The idea is that multiple groups may use completely disjoint kits in LIMS, but want
# to scan based on the REF# etc. So the client sends an additional parameter "group",
# which determines which LIMS kit is used for a given REF#.
GROUP_KIT_NAME_FUNCTION = {
        "Diag": lambda name: "Diag_" + name,
        "NSC": lambda name: "NSC_" + name,
        "TI": lambda name: "TI_" + name,
        "MIK": lambda name: "MIK_" + name,
        None: lambda name: name
        }

kits = {}

def load_kits():
    global kits
    try:
        kit_list = yaml.safe_load(open(kits_file).read())
        kits = dict((str(e['ref']), e) for e in kit_list)
    except IOError as e:
        print("Failed to read kits: ", e)
        kits = {}

if __name__ == '__main__':
    load_kits()

lims_kits = {}

class KitDoesNotExistError(ValueError):
    pass

def get_date_string():
    seq_number_date = datetime.date.today()
    return seq_number_date.strftime("%y%m%d")

def get_lims_kit(name, group=None):
    try:
        kitname = GROUP_KIT_NAME_FUNCTION[group](name)
    except KeyError:
        raise KitDoesNotExistError("Group " + str(group) + " is not known")
    if kitname not in lims_kits:
        try:
            lims_kits[kitname] = lims.get_reagent_kits(name=kitname)[0]
        except IndexError:
            raise KitDoesNotExistError("Kit " + str(kitname) + " does not exist in LIMS")
    return lims_kits[kitname]


@app.route('/kits/<ref>')
def get_kit(ref):
    try:
        kit = kits[ref]
        return jsonify({
                "name": kit['name'],
                "hasUniqueId": kit['hasUniqueId'],
                "found": True,
                "setActive": kit['setActive'],
                "ref": kit['ref']
                })
    except KeyError as e:
        return ("Kit not found", 404)

@app.route('/kits/<group>', methods=['POST'])
def new_kit(group):
    data = request.json
    try:
        ref = data['ref']
        load_kits()
        if data['ref'] in kits:
            return ("Kit " + str(ref) + " already exists", 400)
        try:
            get_lims_kit(data['name'], group)
        except KitDoesNotExistError as e:
            return (str(e), 400)
        kit = {}
        for prop in ['ref', 'hasUniqueId', 'name', 'lotcode', 'setActive']: 
            kit[prop] = data[prop]
        kits[ref] = kit
        try:
            sorted_values = sorted(kits.values(), key=lambda e: e.get('name'))
            open(kits_file, "w").write(yaml.safe_dump(sorted_values))
        except IOError as e:
            if e.errno == 13:
                return ("Access denied to write data file", 403)
            else:
                return ("Unable to write data file", 500)
        return ("OK", 200)

    except KeyError as e:
        return ("Missing field " + str(e) + " in request", 400) 


def get_next_seq_number(kitname, lotcode, group):
    for i in itertools.count(1):
        name = "{0}-{1}-#{2}".format(get_date_string(), lotcode, i)
        lots = lims.get_reagent_lots(kitname=GROUP_KIT_NAME_FUNCTION[group](kitname), name=name)
        if not lots:
            return i


def get_next_name(kit, group):
    if kit['hasUniqueId']:
        return ""
    else:
        seq_number = get_next_seq_number(kit['name'], kit['lotcode'], group)
        return "{0}-{1}-#{2}".format(get_date_string(), kit['lotcode'], seq_number)


@app.route('/lots/<ref>/<lotnumber>/<group>', methods=['GET'])
def get_lot(ref, lotnumber, group):
    """Get information about lots with the requested
    lot number. There may be multiple lots in the system
    with the same lot number, if they have different lot
    names. This method returns the expiry date if available."""

    try:
        kit = kits[ref]
    except KeyError:
        return ("Kit not found", 404)
    try:
        kitname = GROUP_KIT_NAME_FUNCTION[group](kit['name'])
    except KeyError:
        return ("Group not found", 404)
    lots = lims.get_reagent_lots(kitname=kitname, number=lotnumber)
    next_lot_name = get_next_name(kit, group)
    if lots:
        lot = next(iter(lots))
        return jsonify({
		"expiryDate": lot.expiry_date,
		"assignedUniqueId": next_lot_name,
		"uniqueId": next_lot_name,
		"known": True,
		"lotnumber": lotnumber,
		"ref": ref
    	})
    else:
        return jsonify({
		"expiryDate": None,
		"assignedUniqueId": next_lot_name,
		"uniqueId": next_lot_name,
		"known": False,
		"lotnumber": lotnumber,
		"ref": ref
    	})


@app.route('/lots/<ref>/<lotnumber>/<group>', methods=['POST'])
def create_lot(ref, lotnumber, group):
    try:
        kit = kits[ref]
    except KeyError:
        return ("Kit not found", 404)
    data = request.json
    try:
        data_lotnumber = data['lotnumber']
        unique_id = data.get('assignedUniqueId')
        if not unique_id:
            if not kit.get('hasUniqueId'):
                unique_id = get_next_name(kit, group)
            elif kit.get('lotcode'):
                unique_id = "{0}-{1}".format(data['uniqueId'], kit['lotcode'])
            else:
                unique_id = data['uniqueId']
        expiry_date = data['expiryDate'].replace("/", "-"),
    except KeyError as e:
        return ("Missing required field " + str(e), 400)

    if lotnumber != data_lotnumber:
        return ("Lot number does not match URI", 400)
    try:
        lims_kit = get_lims_kit(kit['name'], group)
        dup_lots = lims.get_reagent_lots(kitname=lims_kit.name, name=unique_id, number=lotnumber)
        if dup_lots:
            return ("Error: The lot already exists, with status {}.".format(dup_lots[0].status), 500)

        lot = lims.create_lot(
            lims_kit,
            unique_id,
            lotnumber,
            expiry_date,
            status='ACTIVE' if kit['setActive'] else 'PENDING'
        )
    except requests.HTTPError as e:
        return ("There was a protocol error between the backend and the LIMS server. '{}'".format(e), 500)
    except KitDoesNotExistError as e:
        return (str(e), 500)

    return jsonify({
        "expiryDate": lot.expiry_date,
        "uniqueId": lot.name,
        "assignedUniqueId": lot.name,
        "known": True,
        "lotnumber": lotnumber,
        "ref": ref,
        "limsId": lot.id
        })

@app.route('/editlot/<limsId>', methods=['PUT'])
def edit_lot(limsId):
    data = request.json
    try:
        lot = ReagentLot(lims, id=data['limsId'])
    except KeyError:
        return ("LIMS-ID not specified", 400)
    try:
        lot.get()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return ("Lot does not exist", 404)
        else:
            raise
    
    lot.expiry_date = data['expiryDate'].replace("/", "-")
    lot.name = data['uniqueId']
    lot.lot_number = data['lotnumber']

    lot.put()

    return jsonify({
        "expiryDate": lot.expiry_date,
        "uniqueId": lot.name,
        "assignedUniqueId": lot.name,
        "known": True,
        "lotnumber": lot.lot_number,
        "ref": data['ref'],
        "limsId": lot.id
        })

@app.route('/')
def redir_index():
    return redirect("app/index.html")

if __name__ == '__main__':
    app.debug=True
    app.run(host="0.0.0.0", port=5001)

