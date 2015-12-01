import sys
import getopt
from xml.dom.minidom import parseString
import glsapiutil
from xlrd import open_workbook
from scipy import stats
import xml.etree.ElementTree as ET
import os

HOSTNAME = 'http://192.168.8.10:8080'
VERSION = "v2"
BASE_URI = HOSTNAME + "/api/" + VERSION + "/"

DEBUG = False
api = None
args = None

def findArtifactLUIDSFromProcess():
	## get the XML for the process
	pURI = BASE_URI + "processes/" + args[ "limsid" ]
	pXML = api.getResourceByURI( pURI )
	pDOM = parseString( pXML )
	nodes = pDOM.getElementsByTagName( "input" )
	artifactLUIDS = []
	for n in nodes:
		aLUID = n.getAttribute( "limsid" )
		artifactLUIDS.append( aLUID )
	return artifactLUIDS

def getArtifacts( LUIDs ):

	"""
	This function will be passed a list of artifacts LUIDS, and return those artifacts represented as XML
	The artifacts will be collected in a single batch transaction, and the function will return the XML
	for the entire transactional list
	"""

	lXML = []
	lXML.append( '<ri:links xmlns:ri="http://genologics.com/ri">' )
	for limsid in LUIDs:
		lXML.append( '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>' )
	lXML.append( '</ri:links>' )
	lXML = ''.join( lXML )

	mXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )

	## did we get back anything useful?
	try:
		mDOM = parseString( mXML )
		nodes = mDOM.getElementsByTagName( "art:artifact" )
		if len(nodes) > 0:
			response = mXML
		else:
			response = ""
	except:
		response = ""
	return response


def getSample( LUIDs ):

	"""
	This function will be passed a list of sample LUIDS, and return those samples represented as XML
	The samples will be collected in a single batch transaction, and the function will return the XML
	for the entire transactional list
	"""

	lXML = []
	lXML.append( '<ri:links xmlns:ri="http://genologics.com/ri">' )
	for limsid in LUIDs:
		lXML.append( '<link uri="' + BASE_URI + 'samples/' + limsid + '" rel="samples"/>' )
	lXML.append( '</ri:links>' )
	lXML = ''.join( lXML )

	sXML = api.getBatchResourceByURI( BASE_URI + "samples/batch/retrieve", lXML )
	return sXML

def findControls():
	sample_data = {}
	controlALUIDS =[]
	noncontrolALUIDS =[]
	sample_artifact_map = {}
	sampleLUIDS = []
	arLUIDs = findArtifactLUIDSFromProcess()
	artifactsXML = getArtifacts( arLUIDs )
	## get sample lims id and UDFs from artifacts
	artifacts_root = ET.fromstring( artifactsXML )
	print artifactsXML
	for idx, info in enumerate(artifacts_root.findall("{http://genologics.com/ri/artifact}artifact")):
		aLUID = info.get('limsid')
		sLUID = info.find('sample').attrib["limsid"]
		sample_data['artifact_id'] = aLUID
		sample_artifact_map[sLUID] = aLUID
		sampleLUIDS.append(sLUID)
	saXML = getSample( sampleLUIDS )
	print saXML
	## determine if sample is part of project.  If it is not the sample is a control, and add it to the controlALUIDS list
	sample_root = ET.fromstring( saXML )
	for idx, info in enumerate(sample_root.findall("{http://genologics.com/ri/sample}sample")):
			sLUID = info.attrib["limsid"]
			x = info.find('project')
			if x is None:
				controlALUIDS.append(sample_artifact_map[sLUID])
			else:
				noncontrolALUIDS.append(sample_artifact_map[sLUID])
	return controlALUIDS


def parseFile( filename ):


	global control_dict
	# included sample_dict in case all samples are needed
	global sample_dict

	book = open_workbook( filename, formatting_info=False )
	# only working with first sheet
	sheet = book.sheet_by_index(0)
	COLS = {}
	count = 0
	for col in range(sheet.ncols):
		x = str(sheet.cell(0, count).value)
		COLS[ x ] = count
		count += 1

	control_dict = {}
	sample_dict = {}
	for rows in range(1,sheet.nrows):
		wp = str(sheet.cell(rows, COLS[ "Well" ] ).value)
		value = str(sheet.cell(rows, COLS[ "Fluorescein (0.1s) (Counts)" ] ).value)
		# remove 0 is it is in the well position
		if wp[1] == "0":
			wp = wp[:1] + ':' + wp[2:]
		else:
			wp = wp[:1] + ':' + wp[1:]
		# control locations are predeterimed
		if wp[2] == "1":
			control_dict[wp] = value
		else:
			sample_dict[wp] = value
	# sorted for order
	RFU_keys = sorted( control_dict.keys())
	RFU_values = []
	# expected standard values are hard coded right now.
	RFU_expected = [0, .5, 1, 2, 4, 6, 8, 10]
	# convert values to float and add to list
	for key in RFU_keys:
		RFU_values.append(float (control_dict[key] ))
	print RFU_values
	print RFU_expected
	slope, intercept, r_value, p_value, std_err = stats.linregress( RFU_expected, RFU_values )
	print slope
	print intercept
	print r_value
	print p_value
	print sample_dict
	for key in sample_dict:
		sample_dict[key] = ( float(sample_dict[key]) - intercept ) / slope

def downloadFile():
	#downloads file based on file artifactLUID
	aURI = BASE_URI + "artifacts/" + args[ "filelimsid" ]
	aXML = api.getResourceByURI( aURI )
	aDOM = parseString( aXML )
	fNodes = aDOM.getElementsByTagName( "file:file" )

	if len(fNodes) > 0:
		fLUID = fNodes[0].getAttribute( "limsid" )
		fURI = BASE_URI + "files/" + fLUID
		fXML = api.getResourceByURI( fURI )
		fDOM = parseString (fXML)
		filename = fDOM.getElementsByTagName( "original-location")
		fURI = BASE_URI + "files/" + fLUID + "/download"

		os.system('sox input.wav -b 24 output.aiff rate -v -L -b 90 48k')

		cmd = "/usr/bin/curl --header" + " Content-Disposition:'attachment; filename=" + filename[0].firstChild.nodeValue + "'"  + " -u " + args[ "username" ] + ":" + args[ "password" ] + " -o qPCR.xls  " + fURI
		os.system(cmd )

def doStuff():

	## get the XML for the process
	q_dict = {}
	pURI = BASE_URI + "processes/" + args[ "limsid" ]
	print pURI
	pXML = api.getResourceByURI( pURI )
	pDOM = parseString( pXML )


	nodes = pDOM.getElementsByTagName( "output" )
	aLUIDS = []
	for n in nodes:
		## is this output a individual resultfile?

		ogType = n.getAttribute( "output-generation-type" )
		if ogType == "PerInput":

			## if so, GET it
			aLUID = n.getAttribute( "limsid" )
			aLUIDS.append( aLUID )
	blXML = getArtifacts( aLUIDS )
	blDOM = parseString( blXML )
	nodes = blDOM.getElementsByTagName( "art:artifact" )
	for aDOM in nodes:
		nodes = aDOM.getElementsByTagName( "value" )
		aWP = nodes[0].firstChild.data
		print aWP
		if aWP in sample_dict:
			print sample_dict[aWP]
			api.setUDF( aDOM, "Concentration", sample_dict[aWP] )

	## now update the artifacts
	## now just POST the updated artifacts back to the LIMS
	rXML = api.createObject( blDOM.toxml(), BASE_URI + "artifacts/batch/update" )
	try:
		rDOM = parseString( rXML )
		nodes = rDOM.getElementsByTagName( "link" )
		if len(nodes) > 0:
			print( "Success.")
		else:
			print( "Something has gone wrong!" )
	except:
		print( "Something has gone wrong!" )


def main():

	global api
	global args

	args = {}

	opts, extraparams = getopt.getopt(sys.argv[1:], "l:u:p:f:")

	for o,p in opts:
		if o == '-l':
			args[ "limsid" ] = p
		elif o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-f':
			args[ "filelimsid" ] = p

	api = glsapiutil.glsapiutil()
	api.setHostname( HOSTNAME )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )

	## at this point, we have the parameters the EPP plugin passed, and we have network plumbing
	## so let's get this show on the road!

	downloadFile()
	parseFile("qPCR.xls")
	doStuff()

if __name__ == "__main__":
	main()
