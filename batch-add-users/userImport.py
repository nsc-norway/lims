# This was the example from Genologics Cookbook. 
# Modified to handle a file format more suitable for the NSC.

import sys
import getopt
import glsapiutil
import xml.dom.minidom
from xml.dom.minidom import parseString
import urllib2

VERSION = "v2"

DEBUG = True
api = None
COLS = {}
DATA = []
LABS = {}

def processColumnHeaders( headers ):

	global COLS

	count = 0

	tokens = headers.split( "," )
	for token in tokens:
		COLS[ token ] = count
		count += 1

def parseFile(fileName):

	global DATA

	LINES = []

	f = open( fileName, "r" )
	TEMP = f.readlines()
	f.close()

	headerRow = 3
	lineCount = 1
	for line in TEMP:
		if lineCount >= headerRow:
			if line.startswith( "," ):
				break
			tokens = line.split( "\n" )
			for token in tokens:
				LINES.append( token )
		lineCount += 1

	linecount = 0
	for line in LINES:
		if linecount == 0:
			processColumnHeaders( line )
			linecount += 1
		else:
			if len(line) > 0:
				DATA.append( line )

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

def createUser( uName, fName, lName, eMail, lab ):

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
	uXML += '<password>abcd1234</password>'
	uXML += '<account-locked>false</account-locked><role name="Collaborator"/>'
	uXML += '</credentials>'
	initials = "".join( [name[0] for name in fName.split(" ") + lName.split(" ")] )
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

def importData(fileName, server):

	## step 1: parse the file into data structures:
	parseFile(fileName)
	if DEBUG:
		print COLS
		print DATA[0]

	## step 2: build a data structure that holds the current labs
	getExistingLabs()
	if DEBUG:
		print LABS

	##step 3: start stepping through the file and create labs / users as required
	uNameIndex = COLS[ "User"]
	fnameIndex = COLS[ "First Name" ]
	lNameIndex = COLS[ "Last Name" ]
	eMailIndex = COLS[ "E-mail" ]
	labIndex = COLS[ "Institution" ]
	accessIndex = COLS[ server ]

	for line in DATA:
		tokens = line.split( "," )
		uName = tokens[ uNameIndex ]
		fName = tokens[ fnameIndex ]
		lName = tokens[ lNameIndex ]
		eMail= tokens[ eMailIndex ]
		lab = tokens[ labIndex ]
		accessLevel = tokens[ accessIndex ]

		## is a user with this username already in the system?
		exists = doesUserExist( uName )
		if not exists:
			status = createUser( uName, fName, lName, eMail, lab, accessLevel )
			if status and DEBUG:
				## jump out of the loop after the first successful creation
				break
		else:
			print( "User: " + uName + " already exists in the system.")

def main():

	global api
	global BASE_URI

	args = {}

	opts, extraparams = getopt.getopt(sys.argv[1:], "h:u:p:f:")

	for o,p in opts:
		if o == '-h':
			args[ "host" ] = p
		elif o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-f':
			args[ "fileName" ] = p

	api = glsapiutil.glsapiutil()
	api.setHostname( args[ "host" ] )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )
	BASE_URI = args[ "host" ] + "/api/" + VERSION + "/"

	importData(args['fileName'])


if __name__ == "__main__":
	main()

