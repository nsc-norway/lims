import sys
import zipfile
import datetime
from functools import partial
import StringIO
import requests
from xml.etree.ElementTree import XML
from genologics import config
from genologics.lims import *

WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TABLE_ROW = WORD_NAMESPACE + 'tr'
TABLE_CELL = WORD_NAMESPACE + 'tc'
TEXT = WORD_NAMESPACE + 't'
PARA = WORD_NAMESPACE + 'p'
BR = WORD_NAMESPACE + 'br'
CHECKBOX = WORD_NAMESPACE + 'checkBox'
CHECKED = WORD_NAMESPACE + 'checked'
VAL = WORD_NAMESPACE + 'val'

def samples_received(udfs, val):
    parts = val.split("/")
    if len(parts) == 1:
        parts = val.split(".")
    year, month, day = [int(p) for p in parts]

    return datetime.date()

def total_number_of_tubes(udfs, val):
    udfs["Total # of tubes received"] = int(val)

def storage_location(udfs, val):
    udfs["Storage location"] = val

def lanes(udfs, val):
    pass

def sequencing_type(udfs, val):
    pass

# List of (label, handler)
LABEL_HANDLER = [
        ("Date samples received:", samples_received),
        ("Total number tubes received:", total_number_of_tubes),
        ("Storage location:", storage_location),
        ("Lanes:", lanes),
        ("Type:", sequencing_type),
        ]

# Parsing various inputs
def get_text_single(element):
    val = "".join(t.text for t in element.getiterator(TEXT))
    return val.strip()

def process_dog(tree):
    udf_dict = {}
    for para in tree.getiterator(PARA):
        text = get_text_single(para)
        for label, function in LABEL_HANDLER:
            if text.startswith(label):
                function(udf_dict, text[len(label):].strip())


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    docx_data = None
    try:
        docx_file_output = next(
                f for f in process.all_outputs()
                if f.name.endswith("_ProjectEval") and
                f.type == 'ResultFile'
                )
        if len(docx_file_output.files) == 1:
            docx_file = docx_file_output.files[0]
            docx_data = docx_file.download()
    except StopIteration:
        pass
    if not docx_data:
        # Don't do anything if no submission form...
        #process.udf[ERROR_UDF] = "Sample submission form not found"
        #process.put()
        return

    try:
        document = zipfile.ZipFile(StringIO.StringIO(docx_data))
        xml_content = document.read('word/document.xml')
        tree = XML(xml_content)
        document.close()
    except:
        print "Could not read project evaluation form."
        print ""
        print "Please make sure it is in docx format."
        sys.exit(1)

    try:
        fields = process_dog(tree)
        #for uname, uvalue in fields:
        #    process.udf[uname] = uvalue
    except:
        print "Something went wrong in the main parsing code"
        raise
        #sys.exit(0)

    try:
        process.udf['Project evaluation form processed'] = True
        process.put()
    except requests.exceptions.HTTPError, e:
        # Don't crash on errors
        print "LIMS wouldn't let us fill in the form: " + str(e)
        # Unfortunately, there's no way to report this...

main(sys.argv[1])
