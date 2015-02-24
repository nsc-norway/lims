# Based on the example from Genologics Cookbook. 
# Modified to handle a file format more suitable for the NSC.

import sys
import glsapiutil
import xml.dom.minidom
from xml.dom.minidom import parseString
import urllib2
from argparse import ArgumentParser

VERSION = "v2"

DEBUG = True
api = None
COLS = {}
DATA = []
LABS = {}

def processColumnHeaders( headers ):

	global COLS

	count = 0

	tokens = headers.split( ";" )
	for token in tokens:
		COLS[ token ] = count
		count += 1

def parseFile(fileName):

	global DATA

	f = open( fileName, "r" )
	LINES = [l.strip("\n\r") for l in f.readlines()]
	f.close()

	headerRow = 1

	linecount = 0
	for line in LINES:
		if linecount == headerRow:
			processColumnHeaders( line )
		elif linecount > headerRow:
			if len(line) > 0:
				DATA.append( line )
		linecount += 1

def getExistingLabs():

	global LABS

	lURI = BASE_URI + "labs"
	lXML = api.getResourceByURI( lURI )
	lDOM = parseString( lXML )

	labs = lDOM.getElementsByTagName( "lab" )
	for lab in labs:
		labURI = lab.getAttribute( "uri" )
		nodes = lab.getElementsByTagName( "name" )
		labName = nodes[0].firstChild.data

		LABS[ labName ] = labURI

def doesUserExist( username ):

	qURI = BASE_URI + "researchers?username=" + urllib2.quote( username )
	qXML = api.getResourceByURI( qURI )
	qDOM = parseString( qXML )

	nodes = qDOM.getElementsByTagName( "researcher" )
	if len(nodes) == 0:
		return False
	else:
		return True

def createLab( labName ):

	global LABS

	lXML = '<lab:lab xmlns:lab="http://genologics.com/ri/lab">'
	lXML += '<name>' + labName + '</name>'
	lXML += '</lab:lab>'

	rXML = api.createObject( lXML, BASE_URI + "labs" )
	rDOM = parseString( rXML )
	nodes = rDOM.getElementsByTagName( "lab:lab" )
	if len(nodes) > 0:
		## lab was created, add the details to the dictionary
		lURI = nodes[0].getAttribute( "uri" )
		LABS[ labName ] = lURI
		return True
	else:
		print( "There was a problem creating the lab: " + labName )
		if DEBUG:
			print rXML
		return False

def createUser( uName, fName, lName, eMail, lab, role, password ):

	## does the lab exist, or does it need to be created?
	if len(lab) > 0:
		if lab not in LABS.keys():
			status = createLab( lab )
			if not status:
				print( "Skipping the creation of user: " + uName )

	## now create the user itself
	uXML = '<res:researcher xmlns:res="http://genologics.com/ri/researcher">'
	uXML += '<first-name>' + fName.strip() + '</first-name>'
	uXML += '<last-name>' + lName.strip() + '</last-name>'
	uXML += '<email>' + eMail.strip() + '</email>'
	if len(lab) > 0:
		lURI = LABS[ lab ]
		uXML += '<lab uri="' + lURI + '"/>'
	uXML += '<credentials>'
	uXML += '<username>' + uName.strip() + '</username>'
	uXML += '<password>' + password + '</password>'
	uXML += '<account-locked>false</account-locked><role name="Collaborator"/>'
        uXML += '<role name="' + role + '"/>'
	uXML += '</credentials>'
	initials = "".join( [name[0] for name in fName.split(" ") + lName.split(" ")] )
	while len(initials) < 3:
		initials = initials + "X"
	uXML += '<initials>' + initials + '</initials>'
	uXML += '</res:researcher>'

	rXML = api.createObject( uXML, BASE_URI + "researchers" )
	rDOM = parseString( rXML )
	nodes = rDOM.getElementsByTagName( "res:researcher" )
	if len(nodes) == 0:
		print( "There was a problem creating the user: " + uName )
		if DEBUG:
			print rXML
		return False
	else:
		print( "User: " + uName + " was created successfully" )
		return True

def importData(fileName, server, suffix):

	## step 1: parse the file into data structures:
	parseFile(fileName)

	## step 2: build a data structure that holds the current labs
	getExistingLabs()

	##step 3: start stepping through the file and create labs / users as required
	uNameIndex = COLS[ "Username"]
	fnameIndex = COLS[ "First name" ]
	lNameIndex = COLS[ "Last name" ]
	eMailIndex = COLS[ "E-mail" ]
	labIndex = COLS[ "Lab" ]
	roleIndex = COLS[ server ]

	for line in DATA:
		tokens = line.split( ";" )
		uName = tokens[ uNameIndex ]
		fName = tokens[ fnameIndex ]
		lName = tokens[ lNameIndex ]
		eMail= tokens[ eMailIndex ]
		lab = tokens[ labIndex ]
		role = tokens[ roleIndex ]

		## is a user with this username already in the system?
		print "About to check username " , uName
		exists = doesUserExist( uName )
		if not exists:
			pw = uName + suffix
			status = createUser( uName, fName, lName, eMail, lab, role, pw )
			if status and DEBUG:
				## jump out of the loop after the first successful creation
				break
		else:
			print( "User: " + uName + " already exists in the system.")

def main():

	global api
	global BASE_URI
	parser = ArgumentParser()
	parser.add_argument("--username", help="Your LIMS access username", required = True)
	parser.add_argument("--password", help="Existing password for LIMS (optional)")
	parser.add_argument("--host", help="LIMS server base URL (optional)")
	parser.add_argument("--file-name", help="Name of CSV file with user info", required = True)
	parser.add_argument("--server", help="Short name of LIMS server, corresponds to column in CSV", required = True)
	parser.add_argument("--pw-suffix", help="Temporary password suffix", required = True)
	args = parser.parse_args()
        password = args.password
        if not password:
		password = raw_input("Enter LIMS password: ")
	url = args.host
	if not url:
		host_map = {"sandbox": "https://sandbox-lims.sequencing.uio.no"}
		url = host_map[args.server]

	api = glsapiutil.glsapiutil()
	api.setHostname( url )
	api.setVersion( VERSION )
	api.setup( args.username, password )
	BASE_URI = url + "/api/" + VERSION + "/"

	importData(args.file_name, args.server, args.pw_suffix)


if __name__ == "__main__":
	main()

