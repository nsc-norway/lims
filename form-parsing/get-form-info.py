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

PLACEHOLDER_STRING = "Click here to enter text."


DNA_PREPS = {
        "Regular TruSeqTM adapter ligation": "Regular TruSeq adapter ligation",
        "TruSeqTM PCR-free prep": "TruSeq PCR-free prep",
        "Tagmentation (NexteraTM) sample prep": "Tagmentation Nextera sample prep",
        "I\x60m unsure, please advise": "User unsure"
        }
RNA_PREPS = {
        "Regular TruSeqTM RNA-seq library prep": "Regular TruSeq RNA-seq library prep",
        "Strand-specific TruSeqTM RNA-seq library prep": "Strand-specific TruSeq RNA-seq library prep",
        "small RNA library preparation": "small RNA library preparation",
        "I\x60m unsure, please advise": "User unsure"
        }
SEQUENCING_TYPES = {
        "Single Read": "Single Read",
        "Paired End": "Paired End Read"
        }
SEQUENCING_INSTRUMENTS = {
        "HiSeq 2000": "HiSeq high output",
        "NextSeq 500 (Mid output reagents)": "NextSeq mid output", # WARNING: NextSeq string broken up in docx
        "NextSeq 500 (High output reagents)": "NextSeq high output",
        "MiSeq": "MiSeq"
        }

# Read lengths in LIMS also specify single read / paired end, 
# so this requires post-processing. 
READ_LENGTHS = {
        "35 bp (N, high output only)": 35,
        "50 bp (H, M)": 50,
        "75 bp (N)": 75,
        "100 bp (H, v3 reagents)": 100,
        "125 bp  (H, v4 reagents)": 125,
        "150 bp (M, N)": 150, # unfortunately, broken off at "1"
        "250 bp (M)": 250,
        "300 bp (M)": 300
        }

DEFAULTS = [
        ("Prepaid account", "No"),
        ("Sample prep requested", "None"),
        ("Date samples received", datetime.date.today()),
        ("Reference genome", "-- Not provided --"),
        ("Application", "-- Not provided --"),
        ("Sample type", "-- Not provided --"),
        ("Sample buffer", "-- Not provided --"),
        ("Method used to determine concentration", "-- Not provided --"),
        ("Method used to purify DNA/RNA", "-- Not provided --"),
        ("Contact person", "-- Not provided --"),
        ("Contact email", "-- Not provided --"),
        ("Contact institution", "-- Not provided --"),
        ("Billing institution", "-- Not provided --"),
        ("Billing address", "-- Not provided --"),
        ]

ERROR_UDF = "Submission form processing errors"

# Helper: is checkbox checked
def is_checked(checkbox_elem):
    checked_elem = checkbox_elem.find(CHECKED)
    if not checked_elem is None:
        val = checked_elem.attrib.get(VAL)
        if val == "1":
            return True
        elif val == "0":
            return False
        elif val == None:
            return True
        else:
            raise ValueError("Unexpected value for checkbox: " + val)
    else:
        return False



# Parsing various inputs
def get_text_single(cell):
    val = "".join(t.text for t in cell.getiterator(TEXT))
    if val.strip() == PLACEHOLDER_STRING:
        return None
    else:
        return val.strip()

def get_text_lower(cell):
    val = "".join(t.text for t in cell.getiterator(TEXT))
    if val.strip() == PLACEHOLDER_STRING:
        return None
    else:
        return val.strip().lower()

def get_checkbox(cell):
    checkboxes = cell.getiterator(CHECKBOX)
    if len(checkboxes) == 1:
        return is_checked(checkboxes[0])
    else:
        return None

def get_yes_no_checkbox(cell):
    is_selected = None
    yes_seen = False
    no_seen = False
    for node in cell.getiterator():
        if node.tag == CHECKBOX:
            is_selected = is_checked(node)
        elif node.tag == TEXT and not is_selected is None and node.text.strip() != "":
            text = node.text.strip()
            if text.startswith("Yes"):
                yes_selected = is_selected
                yes_seen = True
            elif text.startswith("No"):
                no_selected = is_selected
                no_seen = True
            is_selected = None

    if yes_seen and no_seen:
        if yes_selected != no_selected:
            return yes_selected

    return None


def single_choice_checkbox(values, cell):
    yes = False
    choice = None
    for node in cell.getiterator():
        if node.tag == CHECKBOX:
            _yes = is_checked(node)
            if yes and _yes:
                return None # Don't allow multiple
            else:
                yes = _yes
            text = ""

        elif yes and node.tag == TEXT:
            text += node.text
            if values:
                choice = values.get(text.strip())
            else:
                choice = node.text.strip()
    return choice


def single_checkbox(value, cell):
    if get_checkbox(cell):
        return value


def get_text_multi(cell):
    text = ""
    first = True
    for node in cell.getiterator():
        if node.tag == PARA:
            if not first:
                text += "\n\n"
            first = False
        elif node.tag == BR:
            text += "\n"
        elif node.tag == TEXT:
            text += node.text

    if text.strip() == PLACEHOLDER_STRING:
        return None
    else:
        return text


def is_library(cell):
    if get_checkbox(cell):
        return "Library"
    else:
        return None


def library_prep_used(cell):
    text_nodes = cell.getiterator(TEXT)
    if len(text_nodes) > 2:
        if text_nodes[0].text.strip() == "If yes, please state which kit / method you used here:":
            return "".join(text_node.text for text_node in text_nodes[1:])
        



def get_portable_hard_drive(cell):
    # First checkbox is User HDD, second is New HDD
    selected = [is_checked(node) for node in cell.getiterator(CHECKBOX)]
    if len(selected) == 2:
        if selected[0] and not selected[1]:
            return "User HDD"
        elif selected[1] and not selected[0]:
            return "New HDD"


# List of (label, udf, parser_func)
LABEL_UDF_PARSER = [
        ("Method used to purify DNA / RNA", 'Method used to purify DNA/RNA', get_text_single),
        ("Method used to determine concentration", 'Method used to determine concentration', get_text_single),
        ("Buffer in which samples dissolved", 'Sample buffer', get_text_single),
        ("Are samples hazardous", 'Hazardous', get_yes_no_checkbox),
        ("Are the samples ready to sequence?", 'Sample type', is_library),
        ("For DNA samples:", 'Sample prep requested', partial(single_choice_checkbox, DNA_PREPS)),
        ("For RNA samples:", 'Sample prep requested', partial(single_choice_checkbox, RNA_PREPS)),
        ("Reference genome; release version:", 'Reference genome', get_text_single),
        ("Sequencing type", 'Sequencing method', partial(single_choice_checkbox, SEQUENCING_TYPES)),
        ("Desired insert size", 'Desired insert size', get_text_single),
        ("Sequencing Instrument requested", 'Sequencing instrument requested', 
            partial(single_choice_checkbox, SEQUENCING_INSTRUMENTS)),
        ("Read Length", 'Read length requested', partial(single_choice_checkbox, READ_LENGTHS)), # Needs post-proc'ing
        ("Total number lanes", 'Total # of lanes requested', get_text_single),
        ("Project Goal", 'Project goal', get_text_multi),
        ("REK approval number", 'REK approval number', get_text_single),
        ("Upload to https site", 'Delivery method', partial(single_checkbox, 'Norstore')),
        ("Portable hard drive", 'Delivery method', get_portable_hard_drive),
        ("Contact Name", 'Contact person', get_text_single),
        ("Institution", 'Institution', get_text_single),# Needs post-processing (Contact / Billing same field name)
        ("Address", 'Contact address', get_text_multi),
        ("Email", 'Email', get_text_lower),         # Needs post-processing
        ("Telephone", 'Telephone', get_text_single), # Needs post-processing
        ("Billing contact person", 'Billing contact person', get_text_single),
        ("Billing Address", 'Billing address', get_text_multi),
        ("Purchase Order Number", 'Purchase order number', get_text_single),
        ("Project is fully or", 'Funded by Norsk Forskningsradet', get_yes_no_checkbox),
        ("Kontostreng", 'Kontostreng (Internal orders only)', get_text_single),
        ("", 'Library prep used', library_prep_used)
        ]


def get_values_from_doc(xml_tree):
    results = []
    for row in xml_tree.getiterator(TABLE_ROW):
        cells = row.getiterator(TABLE_CELL)
        if len(cells) == 2:
            label = get_text_single(cells[0])
            data = cells[1]
            for test_label, udf, parser_func in LABEL_UDF_PARSER:
                if label.startswith(test_label):
                    value = parser_func(data)
                    if not value is None:
                        results.append((udf, value))

    return results


def process_read_length(fields):
    sequencing_method = read_length = None
    for i, f in enumerate(fields):
        if f[0] == 'Sequencing method':
            sequencing_method = f[1]
        elif f[0] == 'Read length requested':
            read_length = f[1]
            read_length_index = i

    if read_length:
        del fields[read_length_index]

    if sequencing_method and read_length:
        if sequencing_method == "Paired End Read":
            num_reads = 2
        elif sequencing_method == "Single Read":
            num_reads = 1
        else:
            return
        fields.append(('Read length requested', "{0}x{1}".format(read_length, num_reads)))
        

def process_contact_billing(fields, field_name, contact_name, billing_name):
    # If there are two instances of the field, the first is contact and the
    # second is billing
    index_instances = [
            (i, f) 
            for i, f in reversed(list(enumerate(fields))) # reversed, so we can del w/o changing indexes
            if f[0] == field_name]
    for (i, f), udfname in zip(index_instances, (billing_name, contact_name)):
        del fields[i]
        if len(index_instances) == 2:
            fields.append((udfname, f[1])) 
    

def process_hazardous(fields):
    for i, f in reversed(list(enumerate(fields))):
        if f[0] == 'Hazardous':
            if f[1]:
                print "Warning: Hazardous samples."
                sys.exit(1)
            else:
                del fields[i]


def remove_duplicates(fields):
    # If there are two entries for a given field (e.g. Delivery or Sample prep), 
    # this is an inconsistent input, and we remove them.
    field_names = [f[0] for f in fields]
    for i, f in reversed(list(enumerate(fields))):
        index = i
        while index:
            try:
                index = field_names.index(f[0], 0, i)
                del fields[index]
                del field_names[index]
            except ValueError:
                index = None


def post_process_values(fields):
    process_read_length(fields)
    process_contact_billing(fields, "Institution", "Contact institution", "Billing institution")
    process_contact_billing(fields, "Email", "Contact email", "Billing email")
    process_contact_billing(fields, "Telephone", "Contact telephone", "Billing telephone")
    process_hazardous(fields)
    remove_duplicates(fields)

def add_defaults(fields):
    field_name_set = set(f[0] for f in fields)
    for key, value in DEFAULTS:
        if not key in field_name_set:
            fields.append((key, value))


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    docx_data = None
    try:
        docx_file_output = next(
                f for f in process.all_outputs()
                if f.name.endswith("SubForm") and
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
        print "Could not read sample submission form."
        print ""
        print "Please convert it to docx format."
        sys.exit(1)

    try:
        fields = get_values_from_doc(tree)
        post_process_values(fields)
        add_defaults(fields)
        for uname, uvalue in fields:
            process.udf[uname] = uvalue
    except:
        print "Something went wrong in the main parsing code"
        sys.exit(0)

    try:
        process.udf['Sample submission form processed'] = True
        process.put()
    except requests.exceptions.HTTPError, e:
        # Don't crash on errors
        print "LIMS wouldn't let us fill in the form: " + str(e)
        # Unfortunately, there's no way to report this...

main(sys.argv[1])
