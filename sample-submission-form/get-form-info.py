import zipfile
import sys
from xml.etree.ElementTree import XML
from genologics import config
from genologics.lims import *

WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TABLE_ROW = WORD_NAMESPACE + 'tr'
TEXT = WORD_NAMESPACE + 't'
PARA = WORD_NAMESPACE + 'p'

def get_checkbox(cell):
    return False

def get_text_single(cell):
    return ""

def get_text_multi(cell):
    return ""

UDF_LABEL_PARSER = [
        ("Method used to purify DNA / RNA", 'Method used to purify DNA/RNA', get_text_single),
        ("Buffer in which samples dissolved", 'Sample buffer', get_text_single)
        ]

def get_values_from_doc(docx_data):
    document = zipfile.ZipFile(docx_data)
    xml_content = document.read('word/document.xml')
    document.close()
    tree = XML(xml_content)
    for node2 in tree.getiterator(TABLE_ROW):
        print node2
    print "Size of data", len(xml_content)
    print "Number of table rows: ", len(tree.findall(TEXT))
    print "Number of p: ", len(tree.findall(PARA))


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    docx_file_output = next(f for f in process.shared_result_files() if f.name.endswith("SubForm"))
    if len(docx_file_output.files) == 1:
        docx_file = docx_file_output.files[0]
        docx_data = docx_file.download()
    else:
        print "Sample submission form not found"
        sys.exit(1)

    udfs = get_values_from_doc(docx_data)
    for uname, uvalue in udfs:
        process.udf[uname] = uvalue

    process.put()


get_values_from_doc(open("/home/paalmbj/sample-submission.docx"))

