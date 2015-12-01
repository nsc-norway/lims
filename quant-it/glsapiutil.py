import urllib2
import re
import sys
import xml.dom.minidom
from xml.dom.minidom import parseString

DEBUG = 0

class glsapiutil:

	## Housekeeping methods

	def __init__( self ):
		if DEBUG > 0: print (self.__module__ + " init called")
		self.hostname = ""
		self.auth_handler = ""
		self.version = "v1"

	def setHostname( self, hostname ):
		if DEBUG > 0: print (self.__module__ + " setHostname called")
		self.hostname = hostname

	def setVersion( self, version ):
		if DEBUG > 0: print (self.__module__ + " setVersion called" )
		self.version = version

	def setup( self, user, password ):

		if DEBUG > 0: print (self.__module__ + " setup called")

		## setup up API plumbing
		password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
		password_manager.add_password( None, self.hostname + '/api/' + self.version, user, password )
		self.auth_handler = urllib2.HTTPBasicAuthHandler(password_manager)
		opener = urllib2.build_opener(self.auth_handler)
		urllib2.install_opener(opener)

	## REST methods

	def createObject( self, xmlObject, url):

		if DEBUG > 0: print (self.__module__ + " createObject called")

		opener = urllib2.build_opener(self.auth_handler)

		req = urllib2.Request(url)
		req.add_data( xmlObject )
		req.get_method = lambda: 'POST'
		req.add_header('Accept', 'application/xml')
		req.add_header('Content-Type', 'application/xml')
		req.add_header('User-Agent', 'Python-urllib2/2.4')

		responseText = "EMPTY"

		try:
			response = opener.open( req )
			responseText = response.read()
		except urllib2.HTTPError, e:
			responseText = e.read()
		except:
			responseText = str(sys.exc_type) + " " + str(sys.exc_value)

		return responseText

	def updateObject( self, xmlObject, url):

		if DEBUG > 0: print (self.__module__ + " updateObject called")

		opener = urllib2.build_opener(self.auth_handler)

		req = urllib2.Request(url)
		req.add_data( xmlObject )
		req.get_method = lambda: 'PUT'
		req.add_header('Accept', 'application/xml')
		req.add_header('Content-Type', 'application/xml')
		req.add_header('User-Agent', 'Python-urllib2/2.4')

		responseText = "EMPTY"

		try:
			response = opener.open( req )
			responseText = response.read()
		except urllib2.HTTPError, e:
			responseText = e.read()
		except:
			responseText = str(sys.exc_type) + " " + str(sys.exc_value)

		return responseText

	def getResourceByURI( self, url ):

		if DEBUG > 0: print (self.__module__ + " getResourceByURI called")

		responseText = ""
		xml = ""

		try:
			xml = urllib2.urlopen( url ).read()
		except urllib2.HTTPError, e:
			responseText = e.read()
		except urllib2.URLError, e:
			responseText = e.read()
		except:
			responseText = str(sys.exc_type) + str(sys.exc_value)

		if len(responseText) > 0:
			print ("Error trying to access " + url)
		###	print (responseText)

		return xml


	def getBatchResourceByURI( self, url, links ):

		if DEBUG > 0: print (self.__module__ + " getBatchResourceByURI called")

		responseText = ""
		xml = ""

		opener = urllib2.build_opener(self.auth_handler)

		req = urllib2.Request(url)
		req.add_data( links )
		req.get_method = lambda: 'POST'
		req.add_header('Accept', 'application/xml')
		req.add_header('Content-Type', 'application/xml')
		req.add_header('User-Agent', 'Python-urllib2/2.4')
		responseText = "EMPTY"

		try:
			response = opener.open( req )
			responseText = response.read()
		except urllib2.HTTPError, e:
			responseText = e.read()
		except:
			responseText = str(sys.exc_type) + " " + str(sys.exc_value)

		return responseText

	## Helper methods

	def getUDF( self, DOM, udfname ):

		response = ""

		elements = DOM.getElementsByTagName( "udf:field" )
		for udf in elements:
			temp = udf.getAttribute( "name" )
			if temp == udfname:
				response = self.getInnerXml( udf.toxml(), "udf:field" )
				break

		return response


	def setUDF( self, DOM, udfname, udfvalue ):

		if DEBUG > 2: print( DOM.toprettyxml() )

		## are we dealing with batch, or non-batch DOMs?
		if DOM.parentNode is None:
			isBatch = False
		else:
			isBatch = True

		newDOM = xml.dom.minidom.getDOMImplementation()
		newDoc = newDOM.createDocument( None, None, None )

		## if the node already exists, delete it
		elements = DOM.getElementsByTagName( "udf:field" )
		for element in elements:
			if element.getAttribute( "name" ) == udfname:
				try:
					if isBatch:
						DOM.removeChild( element )
					else:
						DOM.childNodes[0].removeChild( element )
				except xml.dom.NotFoundErr, e:
					if DEBUG > 0: print( "Unable to Remove existing UDF node" )

				break

		# now add the new UDF node
		txt = newDoc.createTextNode( str( udfvalue ) )
		newNode = newDoc.createElement( "udf:field" )
		newNode.setAttribute( "name", udfname )
		newNode.appendChild( txt )
		if isBatch:
			DOM.appendChild( newNode )
		else:
			DOM.childNodes[0].appendChild( newNode )

		return DOM

	def getParentProcessURIs( self, pURI ):

		response = []

		pXML = self.getResourceByURI( pURI )
		pDOM = parseString( pXML )
		elements = pDOM.getElementsByTagName( "input" )
		for element in elements:
			ppNode = element.getElementsByTagName( "parent-process" )
			ppURI = ppNode[0].getAttribute( "uri" )

			if ppURI not in response:
				response.append( ppURI )

		return response

	def getDaughterProcessURIs( self, pURI ):

		response = []
		outputs = []

		pXML = self.getResourceByURI( pURI )
		pDOM = parseString( pXML )
		elements = pDOM.getElementsByTagName( "output" )
		for element in elements:
			limsid = element.getAttribute( "limsid" )
			if limsid not in outputs:
				outputs.append( limsid )

		## now get the processes run on each output limsid
		for limsid in outputs:
			uri = self.hostname + "/api/" + self.version + "/processes?inputartifactlimsid=" + limsid
			pXML = self.getResourceByURI( uri )
			pDOM = parseString( pXML )
			elements = pDOM.getElementsByTagName( "process" )
			for element in elements:
				dURI = element.getAttribute( "uri" )
				if dURI not in response:
					response.append( dURI )

		return response

	def reportScriptStatus( self, uri, status, message ):

		print uri
		newuri = uri + "/programstatus"
		print newuri
		XML = self.getResourceByURI( newuri )
		newXML = re.sub('(.*<status>)(.*)(<\/status>.*)', '\\1' + status + '\\3', XML)
		newXML = re.sub('(.*<\/status>)(.*)', '\\1' + '<message>' + message + '</message>' + '\\2', newXML)

		response = self.updateObject( newXML, newuri )

	def removeState( self, xml ):

		return re.sub( "(.*)(\?state=[0-9]*)(.*)", "\\1" + "\\3", xml )

	def getInnerXml( self, xml, tag ):
		tagname = '<' + tag + '.*?>'
		inXml = re.sub(tagname, '', xml)

		tagname = '</' + tag + '>'
		inXml = inXml.replace(tagname, '')

		return inXml
