__author__ = 'dcrawford'
# Oct 13th 2016
# File Parsing Script
# This script is useful if a field in the file to be parsed matches exactly the input, or output artifact name, the well location, or an artifact UDF.

# The genericParser.py is provided by Genologics as a framework for developing specific CSV parsers.
# Minimal edits were done to support the FA output file format.

####### Configuration Section #######

# Which row in the file is the column headers?
HeaderRow = 1

# How is file delimited? examples: ',' '\t'
delim = ','

# MAPPING MODE #
# What will we use to map the data to the artifacts in Clarity? ( set ONE of these to True )
MapTo_ArtifactName = False  # matches to name of output artifact
MapTo_WellLocation = True
MapTo_UDFValue = False

if MapTo_UDFValue:      # only if MapTo_UDFValue is True
    UDFName = "CustomerID"      # UDF name in Clarity

MappingColumn = 1       # In which column of the csv file will I find the above information? (Name / Well / UDF /ect.)

# What UDFs are we bringing into Clarity?
artifactUDFMap = {
    # "Column name in file" : "UDF name in Clarity",
    "ng/uL" : "Concentration",
    "nmole/L" : "Molarity",
    "Avg. Size" : "Average Fragment Size"
}


####### End Config #######


import glsfileutil
import glsapiutil
import os
import sys
from xml.dom.minidom import parseString
from optparse import OptionParser
api = None
options = None

artifactUDFResults = {}
DEBUG = False

def parseinputFile():

    data = downloadfile( options.resultLUID )
    columnHeaders = data[HeaderRow - 1].split( delim )

    results = {}
    for i_row, row in enumerate(data[HeaderRow:], HeaderRow + 1):
        values = row.split( delim )
        UDFresults = {}
        for column, UDF in artifactUDFMap.items():
            try:
                UDFresults[ UDF ] = values[ columnHeaders.index( column ) ]
            except ValueError:
                raise ValueError("Error: Column {0} was not found in the headers.".format(column))
            except KeyError:
                raise ValueError("Error: Incorrect number of columns {0} for row {1}.".format(i_row))
        results[ values[ MappingColumn - 1 ]] = UDFresults
    if DEBUG: print results
    return results

def limslogic():

    artifactUDFResults = parseinputFile()
    if DEBUG: print artifactUDFResults

    stepdetails = parseString( api.GET( options.stepURI + "/details" ) ) #GET the input output map
    # print api.GET( options.stepURI + "/details" )
    resultMap = {}

    for iomap in stepdetails.getElementsByTagName( "input-output-map" ):
        output = iomap.getElementsByTagName( "output" )[0]
        if output.getAttribute( "output-generation-type" ) == 'PerInput':
            resultMap[ output.getAttribute( "uri" ) ] = iomap.getElementsByTagName("input")[0].getAttribute( "uri" )
    # resultMap will map the artifact outputs to the artifact inputs

    output_artifacts = parseString( api.getArtifacts( resultMap.keys() ) )
    input_artifacts = parseString( api.getArtifacts( resultMap.values() ) )

    nameMap = {}
    for artDOM in input_artifacts.getElementsByTagName( "art:artifact" ):
        art_URI = artDOM.getAttribute( "uri" )
        nameMap[ art_URI.split("?")[0] ] = artDOM.getElementsByTagName( "name" )[0].firstChild.data

    updated_count = 0
    for artDOM in output_artifacts.getElementsByTagName( "art:artifact" ):
        art_URI = artDOM.getAttribute( "uri" )
        input_name = nameMap[ resultMap[ art_URI.split("?")[0] ] ]
        output_name = artDOM.getElementsByTagName( "name" )[0].firstChild.data
        well = artDOM.getElementsByTagName( "value" )[0].firstChild.data
        try:
            if MapTo_ArtifactName:
                ArtifactUDFs = artifactUDFResults[ output_name ]    # Would need to change this line to input_name if the input artifact name is being matched to instead of output
            elif MapTo_WellLocation:
                #remove the : from the well ( if needed uncomment the following line )
                well = well[0] + well[2:]
                ArtifactUDFs = artifactUDFResults[ well ]
            elif MapTo_UDFValue:
                udfvalue = api.getUDF( artDOM, UDFName )
                if DEBUG: print udfvalue
                ArtifactUDFs = artifactUDFResults[ udfvalue ]

            if DEBUG: print ArtifactUDFs
            for UDF, value in ArtifactUDFs.items():
                api.setUDF( artDOM, UDF, value )
            updated_count += 1
        except:
            pass

    if DEBUG: print output_artifacts.toxml()
    r = api.POST( output_artifacts.toxml(), api.getBaseURI() + "artifacts/batch/update" )
    if DEBUG: print r
    print "The file was parsed successfully,", updated_count, "of", len(resultMap), "samples updated."

def downloadfile( file_art_luid ):

    newName = "temp-" + str( file_art_luid ) + ".txt"
    FH.getFile( file_art_luid, newName )
    if not os.path.exists(newName):
        print "No file attached!"
        sys.exit(1)
    with open( newName, "r") as raw:
        lines = raw.readlines()
    return lines

def setupArguments():

    Parser = OptionParser()
    Parser.add_option('-u', "--username", action='store', dest='username')
    Parser.add_option('-p', "--password", action='store', dest='password')
    Parser.add_option('-s', "--stepURI", action='store', dest='stepURI')
    Parser.add_option('-r', "--resultLUID", action='store', dest='resultLUID')

    return Parser.parse_args()[0]

def main():

    global options
    options = setupArguments()
    global api
    api = glsapiutil.glsapiutil2()
    api.setURI( options.stepURI )
    api.setup( options.username, options.password )
    global FH
    FH = glsfileutil.fileHelper()
    FH.setAPIHandler( api )
    FH.setAPIAuthTokens( options.username, options.password )

    limslogic()

if __name__ == "__main__":
    main()
