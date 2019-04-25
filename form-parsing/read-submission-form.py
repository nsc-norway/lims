# coding=utf-8
import sys
import re
import zipfile
import datetime
from functools import partial
import io
import requests
from xml.etree.ElementTree import XML
if not (len(sys.argv) > 2 and sys.argv[1] == "test"):
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
DEFAULT = WORD_NAMESPACE + 'default'
VAL = WORD_NAMESPACE + 'val'

PLACEHOLDER_STRING = "Click here"


DNA_PREPS = [
        ("Nextera.*Flex", "Nextera Flex"),
        (".*TruSeq.*adapter ligation", "TruSeq Nano"),
        ("TruSeq.*PCR-free prep", "TruSeq PCR-free"),
        ("ThruPLEX", "ThruPLEX"),
        ("16S library prep", "16S prep"),
        (".* unsure, please advise", "User unsure"),
        ]
RNA_PREPS = [
        ("Regular TruSeqTM RNA-seq library prep", "TruSeq Stranded RNA"), # Old form version
        ("Strand-specific TruSeqTM RNA-seq library prep", "TruSeq Stranded RNA"),
        ("small RNA library preparation", "NEBNext miRNA"),
        (".* unsure, please advise", "User unsure")
        ]
SEQUENCING_TYPES = [ # Note: used both in old (single_choice_checkbox) and new
                     # (get_instrument_and_mode) instrument table
        ("Single Read", "Single Read"),
        ("Paired End", "Paired End Read"),
        ]

SEQUENCING_INSTRUMENTS = [
        ("HiSeq X", "HiSeq X"),
        ("HiSeq 4000", "HiSeq 4000"),
        ("HiSeq 3/4000", "HiSeq 4000"),
        ("HiSeq 2500, high output mode", "HiSeq high output"),
        ("HiSeq 2500, rapid mode", "HiSeq rapid mode"),
        ("HiSeq 2000", "HiSeq high output"),
        ("NextSeq .*Mid Output", "NextSeq mid output"), # WARNING: NextSeq string broken up in docx
        ("NextSeq .*High Output", "NextSeq high output"),
        ("MiSeq v2 Micro", "MiSeq v2 Micro"),
        ("MiSeq v2 Nano", "MiSeq v2 Nano"),
        ("MiSeq v2", "MiSeq v2"),
        ("MiSeq v3", "MiSeq v3"),
        ("MiSeq", "MiSeq"),
        ]

# Some defaults are necessary for put() on required fields
DEFAULTS = [
        ("Evaluation type", "-- Select one --"),
        ("Sample prep requested", "None"),
        ("Sample type", "-- Not provided --"),
        ("Reference genome", "-- Not provided --"),
        ("Contact person", "-- Not provided --"),
        ("Contact institution", "-- Not provided --"),
        ("Contact email", "-- Not provided --"),
        ("Billing institution", "-- Not provided --"),
        ("Prepaid account", "No"),
        ("Date samples received", datetime.date.today()),
        ("Sample buffer", "-- Not provided --"),
        ("Method used to purify DNA/RNA", "-- Not provided --"),
        ("Method used to determine concentration", "-- Not provided --"),
        ("Billing address", "-- Not provided --"),
        ]

ERROR_UDF = "Submission form processing errors"

# Helper: is checkbox checked
def is_checked(checkbox_elem):
    checked_elem = checkbox_elem.find(CHECKED)
    if checked_elem is None:
        checked_elem = checkbox_elem.find(DEFAULT)
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
def get_text_multi(cell, check_placeholder=False):
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
    if check_placeholder and re.search(PLACEHOLDER_STRING, text):
        return None
    else:
        return text


def get_text_single(cell, line_sep=",", check_placeholder=True):
    multiline = get_text_multi(cell, check_placeholder=check_placeholder)
    if multiline is None:
        return None
    val = re.sub(r"\n+", ", ", multiline.strip("\n"))
    if check_placeholder and re.search(PLACEHOLDER_STRING, val):
        return None
    else:
        return val.strip().rstrip(".")


def get_text_lower(cell):
    val = get_text_single(cell)
    return val.lower() if val else None


def get_substring(prefix, cell):
    """Get a substring of the cell value. Reads from after prefix, to the next line break"""
    data = get_text_multi(cell)
    if data:
        try:
            substring_index = data.index(prefix)
            value_index = substring_index + len(prefix)
            suffix = data[value_index:]
            val = suffix.partition("\n")[0]
            if val.strip() != PLACEHOLDER_STRING:
                return val
        except (ValueError, IndexError):
            return None


def get_checkbox(cell):
    checkboxes = cell.getiterator(CHECKBOX)
    for cb in checkboxes: # Process only the first checkbox
        return is_checked(cb)
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


def match_key(value_map, partial_key):
    for key_pattern, value in value_map:
        if re.match(key_pattern, partial_key, re.IGNORECASE):
            return value


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
                choice = match_key(values, text.strip())
            else:
                choice = node.text.strip()
    return choice


def read_length(cell):
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
            match = re.match(r" *(\d+) bp", text)
            if match:
                choice = int(match.group(1))
                yes = False # no need to read more

    return choice


def single_checkbox(value, cell):
    if get_checkbox(cell):
        return value


def is_library(cell):
    if get_checkbox(cell):
        return "QC only"
    else:
        return "Prep"


def library_prep_used(cell):
    text_nodes = list(cell.getiterator(TEXT))
    if len(text_nodes) > 2:
        if "If yes, please state which kit / method you used here" in text_nodes[0].text.strip():
            return "".join(text_node.text for text_node in text_nodes[1:])
        

def get_portable_hard_drive(cell):
    # First checkbox is User HDD, second is New HDD
    selected = [is_checked(node) for node in cell.getiterator(CHECKBOX)]
    if len(selected) == 2:
        if selected[0] and not selected[1]:
            return "User HDD"
        elif selected[1] and not selected[0]:
            return "New HDD"


def get_delivery_method(cell):
    # First checkbox is User HDD, second is New HDD
    selected = [is_checked(node) for node in cell.getiterator(CHECKBOX)]
    if (len(selected) in [4,5]) and sum(1 for s in selected if s) == 1: 
        try:
            return ["Norstore", "NeLS project", "User HDD", "New HDD", "TSD project"][selected.index(True)]
        except IndexError:
            return None


def get_seq_types_read_lengths(single_read_cell, paired_end_cell):
    """Called on two cells of the header row of the table, to find a list of
        tuples (sequencing type, read length), one for each column of the
        following table."""
    # First version of submission form:
    columns = []
    for cell, (seq_type_text, seq_type_val), n_reads in zip(
            [single_read_cell, paired_end_cell],
            SEQUENCING_TYPES,
            [1,2]):
        seq_type, _, read_lengths = get_text_single(cell, check_placeholder=False).partition(",")
        if seq_type.strip().lower() != seq_type_text.strip().lower() or read_lengths.strip() == "":
            return None
        else:
            for read_length in read_lengths.split():
                try:
                    columns.append((seq_type_val, "{}x{}".format(int(read_length), n_reads)))
                except ValueError:
                    return None
    return columns


def get_instrument_and_mode(instrument_output_table, cells):
    row_label = get_text_single(cells[0], check_placeholder=False)
    instrument_string = row_label.partition(",")[0].strip()
    instrument = None
    for pattern, x_instrument in SEQUENCING_INSTRUMENTS:
        if re.match(pattern, instrument_string, re.IGNORECASE):
            instrument = x_instrument
            break
    selected = None
    for values, cell in zip(instrument_output_table, cells[1:]):
        if get_checkbox(cell):
            if selected:
                return None # Multiple selected
            else:
                selected = values

    if instrument and selected:
        return (
                ('Sequencing instrument requested', instrument),
                ('Sequencing method',               selected[0]),
                ('Read length requested',           selected[1]),
                )
    else:
        return None


# List of (label, udf, parser_func)
LABEL_UDF_PARSER = [
        ("Method used to purify DNA / RNA", 'Method used to purify DNA/RNA', get_text_single),
        ("Method used to determine concentration", 'Method used to determine concentration', get_text_single),
        ("Buffer in which samples dissolved", 'Sample buffer', get_text_single),
        ("Are samples hazardous", 'Hazardous', get_yes_no_checkbox),
        ("Are the samples ready to sequence?", 'Evaluation type', is_library),
        ("For DNA samples", 'Sample prep requested', partial(single_choice_checkbox, DNA_PREPS)),
        ("For RNA samples", 'Sample prep requested', partial(single_choice_checkbox, RNA_PREPS)),
        ("Species:", 'Species', get_text_single),
        ("Reference genome", 'Reference genome', get_text_single),
        ("Sequencing type", 'Sequencing method', partial(single_choice_checkbox, SEQUENCING_TYPES)),
        ("Desired insert size", 'Desired insert size', get_text_single),
        ("Sequencing Instrument requested", 'Sequencing instrument requested', 
            partial(single_choice_checkbox, SEQUENCING_INSTRUMENTS)), # <2019-04 seq instrument
        ("Read Length", 'Read length TEMPFIELD', read_length),        # <2019-04 read length; Needs post-proc'ing
        ("Total number lanes", 'Total # of lanes requested', get_text_single),
        ("Project Goal", 'Project goal', get_text_multi),
        ("REK approval number", 'REK approval number', get_text_single),
        ("Upload to https site", 'Delivery method', partial(single_checkbox, 'Norstore')), # Support old form versions
        ("Portable hard drive", 'Delivery method', get_portable_hard_drive),    # Support old form versions
        ("Upload to https site", 'Delivery method', get_delivery_method),       # New delivery method table
        ("Contact Name", 'Contact person', get_text_single),
        ("Institution", 'Institution', get_text_single),# Needs post-processing (Contact / Billing same field name)
        ("Address", 'Contact address', get_text_multi),
        ("Email", 'Email', get_text_lower),         # Needs post-processing
        ("Telephone", 'Telephone', get_text_single), # Needs post-processing
        ("Billing contact person", 'Billing contact person', get_text_single),
        ("Billing Address", 'Billing address', get_text_multi),
        ("Postcode", 'Billing postcode', get_text_single),
        ("Purchase Order Number", 'Purchase order number', get_text_single),
        ("Project is fully or", 'Funded by Norsk Forskningsradet', get_yes_no_checkbox),
        ("Kontostreng", 'Kontostreng (Internal orders only)', get_text_single),
        ("", 'Library prep used', library_prep_used)
        ]


LABEL_CONTENT_UDF_PARSER = [
        ("Upload to https site", 'NeLS project identifier', partial(get_substring, "please enter it here: ")),
        ]


def get_values_from_doc(xml_tree):
    results = []
    instrument_output_table = None
    instrument_udfs = []
    instruments_found = 0
    for row in xml_tree.getiterator(TABLE_ROW):
        cells = list(row.getiterator(TABLE_CELL))
        if cells:
            label = get_text_single(cells[0], check_placeholder=False)
            # Row-by-row parsing for tables with two columns, based on matching strings
            # in the first column
            if len(cells) == 2:
                data = cells[1]
                for test_label, udf, parser_func in LABEL_UDF_PARSER:
                    if re.match(test_label, label, re.IGNORECASE):
                        value = parser_func(data)
                        if not value is None:
                            results.append((udf, value))
                for test_label, udf, parser_func in LABEL_CONTENT_UDF_PARSER:
                    if re.match(test_label, label, re.IGNORECASE):
                        value = parser_func(cells[0])
                        if not value is None:
                            results.append((udf, value))
            # Instrument / Output table has many columns and can't be parsed using the normal
            # framework. Stateful parsing based on first looking for the header row, then the
            # per-instrument rows.
            elif len(cells) == 3:
                if label == "Instrument / output size":
                    instrument_output_table = get_seq_types_read_lengths(*cells[1:])
            elif instrument_output_table and len(cells) == len(instrument_output_table)+1:
                instrument_udfs_tmp = get_instrument_and_mode(instrument_output_table, cells)
                if instrument_udfs_tmp:
                    instruments_found += 1
                    instrument_udfs = instrument_udfs_tmp
    if instruments_found == 1:
        results += instrument_udfs
    return results


def process_read_length(fields):
    sequencing_method = read_length = None
    for i, f in enumerate(fields):
        if f[0] == 'Sequencing method':
            sequencing_method = f[1]
        elif f[0] == 'Read length TEMPFIELD':
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
                print("Warning: Hazardous samples. Can't do anything.")
                del fields[i]
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



def parse(docx_data):
    try:
        document = zipfile.ZipFile(io.BytesIO(docx_data))
        xml_content = document.read('word/document.xml')
        tree = XML(xml_content)
        document.close()
    except:
        raise RuntimeError("Could not read sample submission form. Please convert it to docx format.")

    fields = get_values_from_doc(tree)
    post_process_values(fields)
    add_defaults(fields)
    return fields


def main(process_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)
    program_status = Step(lims, id=process_id).program_status
    docx_data = None
    try:
        docx_file_output = next(
                f for f in process.all_outputs()
                if f.name.endswith("SubForm") and
                f.type == 'ResultFile'
                )
        if len(docx_file_output.files) == 1:
            docx_file = docx_file_output.files[0]
            if docx_file.original_location.endswith(".docx"):
                docx_data = docx_file.download()
            else:
                print("Error: Submission form has incorrect file extension, should be docx.")
                return 1
    except StopIteration:
        pass
    if not docx_data:
        # Don't do anything if no submission form...
        program_status.message = "Sample submission form not found, continuing."
        program_status.status = "WARNING"
        program_status.put()
        return 0

    try:
        fields = parse(docx_data)
    except RuntimeError as e:
        print(e)
        return 1
    for uname, uvalue in fields:
        process.udf[uname] = uvalue

    try:
        process.udf['Sample submission form imported'] = True
        process.put()
        print("Submission form imported successfully.")
    except requests.exceptions.HTTPError as e:
        print("Error while updating fields: {}.".format(e))
        return 1
    return 0

def test(filename):
    with open(filename, 'rb') as f:
        data = f.read()
        fields = parse(data)
        for key, value in sorted(fields):
            print ("{0:20}: {1}".format(key, value))


if sys.argv[1] == "test":
    test(sys.argv[2])
else:
    sys.exit(main(sys.argv[1]))

