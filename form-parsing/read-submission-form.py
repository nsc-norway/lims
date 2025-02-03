# coding=utf-8
import sys
import re
import zipfile
import datetime
from functools import partial
import itertools
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
# Newer versions of Word make checkboxes with different tags. The parser
# supports both kinds of checkbox (get_checkbox function).
WORD_NAMESPACE_2 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
CHECKBOX_2 = WORD_NAMESPACE_2 + 'checkbox' # Note lowercase "b"
CHECKED_2 = WORD_NAMESPACE_2 + 'checked'
DEFAULT_ = WORD_NAMESPACE_2 + 'default'
VAL_2 = WORD_NAMESPACE_2 + 'val'

PLACEHOLDER_STRINGS = [
    "Click.*here.*left.*of.*box",
    "Click.*here.*to.*enter.*text"
]


DNA_PREPS = [
        ("Nextera.*Flex", "Nextera Flex"),           # < v17.1 Previous versions
        ("Illumina.*DNA Prep", "Illumina DNA Prep"), # >= v17.1 Replaces Nextera Flex
        (".*TruSeq.*adapter ligation", "TruSeq Nano"),
        (".*TruSeq.*Nano DNA.*prep", "TruSeq Nano"), # >= v17.1 Matching
        ("TruSeq.*PCR-free prep", "TruSeq PCR-free"),
        (".*ThruPLEX.*", "ThruPLEX"),
        ("16S library prep", "16S prep"),
        ("Swift 2S Turbo", "Swift 2S Turbo"),
        ("Swift 2S Sonic", "Swift 2S Sonic"),
        (".* unsure, please advise", "User unsure"),
        ]
RNA_PREPS = [
        ("Regular TruSeqTM RNA-seq library prep", "TruSeq Stranded RNA"), # Old form version
        (".*TruSeq.*mRNA.*", "TruSeq Stranded mRNA"),
        (".*TruSeq.*total.*RNA.*QiaSeq FastSelect.*", "TruSeq Stranded total RNA + FastSelect rRNA/Globin Depletion"),
        (".*TruSeq.*total.*RNA-seq library prep$", "TruSeq Stranded total RNA"),        # This has to be AFTER rRNA depletion,
        ("Strand-specific TruSeqTM RNA-seq library prep", "TruSeq Stranded RNA"), # Pre v.15: Not separate total/mRNA
        (".*QiaSeq miRNA.*", "QiaSeq miRNA"),                           # >= v17.1: Note this choice needs to be before the
                                                                        # next line "NEBnext", as otherwise the text will
                                                                        # match the NEBnext string instead.
        ("small RNA library preparation", "NEBNext miRNA"),
        (".* unsure, please advise", "User unsure")
        ]
SEQUENCING_TYPES = [ # Note: used both in old (single_choice_checkbox) and new
                     # (get_instrument_and_mode) instrument table
        ("Single Read", "Single Read"),
        ("Paired End", "Paired End Read"),
        ]

SEQUENCING_TYPES_v17 = {
    "SR": "Single Read",
    "PE": "Paired End Read",
}

# The following list is deprecated since form version v17.1. In the new form we use the function
# get_instrument_and_mode_v17, which contains the sequencer types within it.
# The second elements of the tuples in here correspond to the UDF values entered into LIMS,
# and the same values should also be used in get_instrument_and_mode_v17. An exception
# is NovaSeq X, which was only added in v17.1 and is not included here.
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
        ("NovaSeq SP.*½", "NovaSeq SP ½"),
        ("NovaSeq SP", "NovaSeq SP"),
        ("NovaSeq S1.*½", "NovaSeq S1 ½"),
        ("NovaSeq S1", "NovaSeq S1"),
        ("NovaSeq S2.*½", "NovaSeq S2 ½"),
        ("NovaSeq S2", "NovaSeq S2"),
        ("NovaSeq S4.*¼", "NovaSeq S4 ¼"),
        ("NovaSeq S4", "NovaSeq S4"),
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
        checked_elem = checkbox_elem.find(CHECKED_2)
    elif checked_elem is None:
        checked_elem = checkbox_elem.find(DEFAULT)
    elif checked_elem is None:
        checked_elem = checkbox_elem.find(DEFAULT_2)
    if not checked_elem is None:
        val = checked_elem.attrib.get(VAL)
        if val is None:
            val = checked_elem.attrib.get(VAL_2)
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


def is_placeholder(text):
    return any(re.search(ph, text) for ph in PLACEHOLDER_STRINGS)


# Parsing various inputs
def get_text_multi(cell, check_placeholder=True):
    text = ""
    first = True
    for node in cell.iter():
        if node.tag == PARA:
            if not first:
                text += "\n\n"
            first = False
        elif node.tag == BR:
            text += "\n"
        elif node.tag == TEXT:
            text += node.text
    if check_placeholder and is_placeholder(text):
        return None
    else:
        return text


def get_text_single(cell, line_sep=",", check_placeholder=True):
    multiline = get_text_multi(cell, check_placeholder=check_placeholder)
    if multiline is None:
        return None
    val = re.sub(r"\n+", ", ", multiline.strip("\n"))
    if check_placeholder and is_placeholder(val):
        return None
    else:
        return val.strip().rstrip(".")


def get_text_lower(cell):
    val = get_text_single(cell)
    return val.lower() if val else None


def get_substring(prefix, cell):
    """Get a substring of the cell value. Reads from after prefix, to the next line break"""
    data = get_text_multi(cell, check_placeholder=False)
    if data:
        try:
            substring_index = data.index(prefix)
            value_index = substring_index + len(prefix)
            suffix = data[value_index:]
            val = suffix.partition("\n")[0]
            if not is_placeholder(val):
                return val
        except (ValueError, IndexError):
            return None

def find_checkbox_elements(cell):
    return 


def get_checkbox(cell):
    checkboxes = itertools.chain(cell.iter(CHECKBOX), cell.iter(CHECKBOX_2))
    for cb in checkboxes: # Process only the first checkbox
        return is_checked(cb)
    return None


def get_yes_no_checkbox(cell):
    is_selected = None
    yes_seen = False
    no_seen = False
    for node in cell.iter():
        if node.tag in [CHECKBOX, CHECKBOX_2]:
            is_selected = is_checked(node)
        elif node.tag == TEXT and (not is_selected is None) and (node.text.strip() != ""):
            text = node.text.strip()
            found_answer = False
            if text.startswith("Yes"):
                yes_selected = is_selected
                yes_seen = True
                found_answer = True
            elif text.startswith("No"):
                no_selected = is_selected
                no_seen = True
                found_answer = True
            if found_answer:
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
    for node in cell.iter():
        if node.tag in [CHECKBOX, CHECKBOX_2]:
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
    for node in cell.iter():
        if node.tag in [CHECKBOX, CHECKBOX_2]:
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
    """Returns value if the cell contains a single checkbox and it is checked.

    This function was fixed in the v17.1 form parser so it doesn't match if there are
    multiple checkboxes in the cell.
    """
    checkboxes = list(cell.iter(CHECKBOX)) + list(cell.iter(CHECKBOX_2))
    if len(checkboxes) == 1:
        if is_checked(checkboxes[0]):
            return value
    elif "".join([node.text for node in cell.iter(TEXT)]).strip() in ["x", "☒"]:
        return value


def is_library(cell):
    if get_checkbox(cell):
        return "QC only"
    else:
        return "Prep"


def library_prep_used(cell):
    text_nodes = list(cell.iter(TEXT))
    if len(text_nodes) >= 1:
        prompt = "If yes, please state which kit / method you used here:"
        if prompt in text_nodes[0].text.strip():
            data = "".join(text_node.text for text_node in text_nodes)[len(prompt):].strip()
            if not is_placeholder(data):
                return data
    # New prompt / box. The text elements are split so that the first letter is in a
    # separate cell. The answer is always expected to be in a separete element from the
    # prompt.
    text_elements = [node.text for node in text_nodes]
    prompt = "tate which kit / method used"
    i = -1 # Set a default in case there are no text elemnets (old form)
    for i, element in enumerate(text_elements):
        if prompt in element:
            break
    if len(text_elements) < i+2: # There should always be several text cells after this prompt
                                 # This will also return if the prompt is not found
        return None
    if text_elements[i+1] == ".": # Skip full stop after prompt (in separate element)
        i += 1
    answer = ""
    for element in text_elements[i+1:]:
        if element == '☐':
            return answer.strip()
        answer += element
    return None


def get_portable_hard_drive(cell):
    # First checkbox is User HDD, second is New HDD
    selected = [is_checked(node) for node in itertools.chain(cell.iter(CHECKBOX), cell.iter(CHECKBOX_2))]
    if len(selected) == 2:
        if selected[0] and not selected[1]:
            return "User HDD"
        elif selected[1] and not selected[0]:
            return "New HDD"


def get_delivery_method(cell):
    selected = [is_checked(node) for node in itertools.chain(cell.iter(CHECKBOX), cell.iter(CHECKBOX_2))]
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


def cleanup_seq_table_string(s):
    """Gets the text contents of a string, for the strings in the sequencer table.
    
    First pick out anything before open parenthesis if present. Then replace
    every non-alphanumeric character with spaces, then collapse all whitespaces to
    single spaces, and finally remove leading & trailing spaces.
    """

    pre_parens = s.split("(", maxsplit=1)[0]
    replaced = re.sub(r"[^A-Za-z0-9]", " ", pre_parens)
    collapsed = re.sub(r"\s+", " ", replaced)
    return collapsed.strip()


def get_read_length_and_sequencing_type(read_length_string):
    """Parse fixed-format values like '150 bp PE'."""

    m = re.match(r"(\d+) bp ([A-Z]{2})$", read_length_string)
    if m:
        read_length = m.group(1) # Report as numeric string
        seq_method = m.group(2)  # PE or SR
        if seq_method in SEQUENCING_TYPES_v17:
            return (read_length, SEQUENCING_TYPES_v17[seq_method])
    return None, None


def get_instrument_and_mode_v17(instrument_string, cells):
    """Process a row of the table, corresponding to a sequencer and mode.
    This operates on v17.1 of the form.

    If the mode's checkbox (col 2) is ticked, the information about sequencer,
    mode and read length is extracted and returned. The fourth column, for the
    number of lanes, is ignored. The checkbox next to the seqencer name is
    ignored.

    Returns None if this row is not selected.
    """

    if get_checkbox(cells[1]):
        # Don't get the instrument (the commented line below). Instead it is provided
        # as an argument.
        #instrument_string = get_text_single(cells[0])
        instrument = cleanup_seq_table_string(instrument_string)
        mode = cleanup_seq_table_string(get_text_single(cells[1]))

        # For backward compat, replace NovaSeq 6000 with NovaSeq
        if instrument == "NovaSeq 6000":
            instrument = "NovaSeq"
        
        result = [
            ('Sequencing instrument requested', instrument + " " + mode)
        ]

        read_length, seq_meth = get_read_length_and_sequencing_type(get_text_single(cells[2]))
        if read_length and seq_meth:
            result.append(('Read length requested', read_length))
            result.append(('Sequencing method', seq_meth))

        return result
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
        ("Species", 'Species', get_text_single),
        ("Reference genome", 'Reference genome', get_text_single),
        ("Sequencing type", 'Sequencing method', partial(single_choice_checkbox, SEQUENCING_TYPES)),
        ("Desired insert size", 'Desired insert size', get_text_single), # >=v17.1: Option removed in current version
        ("Sequencing Instrument requested", 'Sequencing instrument requested', 
            partial(single_choice_checkbox, SEQUENCING_INSTRUMENTS)), # <2019-04 seq instrument
        ("Read Length", 'Read length TEMPFIELD', read_length),        # <2019-04 read length; Needs post-proc'ing
        ("Total number lanes", 'Total # of lanes requested', get_text_single),
        ("Total number runs requested", 'Total # of lanes requested', get_text_single), # >= v1.17: New text. Uses the top level item.
        ("Project Goal", 'Project goal', get_text_multi),
        ("REK approval number", 'REK approval number', get_text_single),
        ("Upload to https site", 'Delivery method', partial(single_checkbox, 'Norstore')), # Support old form versions
        ("Portable hard drive", 'Delivery method', get_portable_hard_drive),    # Support old form versions
        ("Upload to https site", 'Delivery method', get_delivery_method),       # New delivery method table (but before v17.1)
        ("Upload to NIRD", 'Delivery method', partial(single_checkbox, 'Norstore')),    # BEGIN Newer v17.1 delivery method table, separate rows
        ("Upload to NeLS", 'Delivery method', partial(single_checkbox, 'NeLS project')), 
        ("Upload to NeLS", "NeLS project identifier", partial(get_substring, 'Existing project')),
        (r"Portable hard drive \(exFAT format\), Provided by user", 'Delivery method', partial(single_checkbox, 'User HDD')),
        (r"Portable hard drive \(exFAT format\), provided by NSC", 'Delivery method', partial(single_checkbox, 'New HDD')),
        ("Upload to TSD", 'Delivery method', partial(single_checkbox, 'TSD roject')),   # END v17.1 table
        ("If you want to get primary data analysis", 'Bioinformatic services', get_checkbox),
        ("Contact Name", 'Contact person', get_text_single),
        ("Institution:", 'Institution', get_text_single),# Needs post-processing (Contact / Billing same field name)
                                                         # Pre-v17.1: Search for trailing colon to ignore the VAT field
        ("Institution$", 'Institution', get_text_single),# >= v17.1: Require complete match (end of string character)
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
    # Keep information from previous rows for merged cells in the v17.1 sequencer table.
    current_instrument_string_formv17 = None
    for row in xml_tree.iter(TABLE_ROW):
        cells = list(row.iter(TABLE_CELL))
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
            # framework.
            # Pre-v17.1 form has three columns.
            # Stateful parsing based on first looking for the header row, then the
            # per-instrument rows.
            # Post-v17.1: Stateful parsing based on rows
            elif len(cells) == 3:
                if label == "Instrument / output size":
                    instrument_output_table = get_seq_types_read_lengths(*cells[1:])
            elif instrument_output_table and len(cells) == len(instrument_output_table)+1:
                instrument_udfs_tmp = get_instrument_and_mode(instrument_output_table, cells)
                if instrument_udfs_tmp:
                    instruments_found += 1
                    instrument_udfs = instrument_udfs_tmp
            elif len(cells) == 4: # v17.1 New Sequencing table (will also process and ignore the header row)
                instrument = get_text_single(cells[0])
                if instrument:
                    current_instrument_string_formv17 = instrument
                instrument_udfs_tmp = get_instrument_and_mode_v17(current_instrument_string_formv17, cells)
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
    # If there are two instances of the field (field_name), the first is contact and the
    # second is billing. If there's one instance only, we can put it as "contact".

    # First argument fields should be a list of (key, value) tuples.

    # Create a list of all indexes in the list matching this field name. Last first.
    index_instances = [
            (i, f) 
            for i, f in reversed(list(enumerate(fields))) # reversed, so we can del w/o changing indexes
            if f[0] == field_name]

    # Now spread these into two UDFs, or just add contact if there's one
    if len(index_instances) == 2:
        del fields[index_instances[0][0]]
        fields.append((billing_name, index_instances[0][1][1]))
        del fields[index_instances[1][0]]
        fields.append((contact_name, index_instances[1][1][1]))
    elif len(index_instances) == 1:
        del fields[index_instances[0][0]]
        fields.append((contact_name, index_instances[0][1][1]))
    else:
        for (i, f) in index_instances:
            del fields[i]
    

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
            try:
                print ("{0:20}: {1}".format(key, value))
            except UnicodeEncodeError:
                print ("{0:20}: <unicode error, skipped in test mode>".format(key))


if sys.argv[1] == "test":
    test(sys.argv[2])
else:
    sys.exit(main(sys.argv[1]))

