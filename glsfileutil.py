import glsapiutil
import os

from xml.dom.minidom import parseString

####################################################################
## THESE CLASS RELIES UPON THE glsapiutil2 CLASS
####################################################################

DEBUG = True

class fileHelper:

	def __init__( self):
		self.__api = None
		self.__apiUsername = ""
		self.__apiPassword = ""

	def setAPIHandler( self, object ):
		self.__api = object

	def setAPIAuthTokens( self, username, password ):
		self.__apiUsername = username
		self.__apiPassword = password

	def getFile( self, rfLUID, filePath ):

		## get the details from the resultfile artifact
		aURI = self.__api.getBaseURI() + "artifacts/" + rfLUID
		if DEBUG is True:
			print( "Trying to lookup:" + aURI )
		aXML = self.__api.GET( aURI )
		aDOM = parseString( aXML )

		## get the file's details
		nodes = aDOM.getElementsByTagName( "file:file" )
		if len(nodes) > 0:
			fLUID = nodes[0].getAttribute( "limsid" )
			dlURI = self.__api.getBaseURI() + "files/" + fLUID + "/download"
			if DEBUG is True:
				print( "Trying to download:" + dlURI )

			dlFile = self.__api.GET( dlURI )

			## write it to disk
			try:
				f = open( "./" + filePath, "w" )
				f.write( dlFile )
				f.close()
			except:
				if DEBUG is True:
					print( "Unable to write downloaded file to %s" % filePath )


	def putFile( self, rfLUID, filename ):

		## get the details from the resultfile artifact
		aURI = self.__api.getBaseURI() + "artifacts/" + rfLUID
		if DEBUG is True:
			print( "Trying to lookup:" + aURI )
		aXML = self.__api.GET( aURI )
		aDOM = parseString( aXML )

		## get the file's details
		fNodes = aDOM.getElementsByTagName( "file:file" )
		if len(fNodes) > 0:
			fLUID = fNodes[0].getAttribute( "limsid" )
			ulURI = self.__api.getBaseURI() + "files/" + fLUID + "/upload"

			cmd = "/usr/bin/curl -F file=@%s -u %s:%s %s" % ( "./" + filename, self.__apiUsername, self.__apiPassword, ulURI )
			print( cmd )
			os.system( cmd )

		print( "Replaced File: %s" % filename )