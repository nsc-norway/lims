import re
import os
import sys
import yaml
import datetime
import subprocess
import requests
# Import LIMS packages if not in test mode
if len(sys.argv) != 2 or sys.argv[1] != "test":
    from genologics import config
    from genologics.lims import *


transforms = {
    'first_line':       lambda x: x.splitlines()[0],
    'skip_first_line':  lambda x: '\n'.join(x.splitlines()[1:]),
    'todays_date':      lambda x: datetime.date.today()
}

def main(process_id, test=False):
    script_dir = os.path.dirname(os.path.realpath(__file__))

    with open(os.path.join(script_dir, 'config.yaml')) as conffile:
        conf = yaml.safe_load(conffile)

    if test:
        docx_data = open(process_id, 'rb').read()
    else:
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
                    # Given that we fallback to the previous parser, we shouldn't output a message here, and instead
                    # rely on the old parser to fail in the same way and print the error about file extension.
                    # TODO: If ever retiring the old format for good, uncomment this error message:
                    #print("Error: Submission form has incorrect file extension, should be docx.")
                    return 1
        except StopIteration:
            pass

    if not docx_data:
        # Don't do anything if no submission form...
        program_status.message = "Sample submission form not found, continuing."
        program_status.status = "WARNING"
        program_status.put()
        return 0

    # Convert to text data using perl script docx2txt
    perl_cmd = ["perl", "-I", script_dir, os.path.join(script_dir, "docx2txt.pl")]
    p = subprocess.run(perl_cmd,
                stdout=subprocess.PIPE,
                input=docx_data)
    if p.returncode != 0:
        print("-- Exiting due to the error reported above by docx2txt. --")
        return 1
    input_data = p.stdout

    text = input_data.decode('utf8')
    if not 'nettskjema' in text:
        print("Not Nettskjema, returning an error status to fall back to the old script")
        return 1

    lines = text.splitlines()

    # First line of answers have a leading space with something
    # non-spacey after it
    plain_text_format = False
    answer_first_line_numbers = [
            i
            for i, l in enumerate(lines)
            if re.match(r" .*[^ ].*", l)
            ]
    if len(answer_first_line_numbers) < 3:
        # We have too few answers. The format can be something different, using asterisks
        # and not space at the start of the line. This results from copying and pasting the
        # contents from MS-Outlook's simple view: without enabling the full graphical view of
        # the message.
        plain_text_format = True
        answer_first_line_numbers = [
                i
                for i, l in enumerate(lines)
                if re.match(r"\*[ \t]+[^\t ]", l)
                ]
    
    # This preliminary stage just gets the full question and answer
    # texts
    qas = []
    for ans_start_line in answer_first_line_numbers:
            if ans_start_line == 0: continue # First line, nothing

            # Look behind for question text up to blank line
            q_start_line = ans_start_line - 1
            if plain_text_format:
                while q_start_line - 1 > 0 and not lines[q_start_line - 1].startswith('*'):
                        q_start_line -= 1
            else:
                while q_start_line - 1 > 0 and lines[q_start_line - 1] != '':
                        q_start_line -= 1
            # Get question
            question = "\n".join(k.strip() for k in lines[q_start_line:ans_start_line])

            # Take lines until a blank line comes
            ans_end_line = ans_start_line
            while ans_end_line + 1 < len(lines) and lines[ans_end_line+1] != '':
                    ans_end_line += 1
            # Get answer
            answer = "\n".join(k.strip() for k in lines[ans_start_line:ans_end_line+1])
            # Remove hyperlink annotations made by docx2txt
            answer = re.sub(r" \[HYPERLINK: [^\]]+\]", "", answer)
            # Remove leading asterisk and tab/space -- asterisk plain text format
            answer = re.sub(r"^\*[ \t]+", "", answer)
            qas.append((question, answer))
    udfs_to_set = {}
    for question in conf['questions']:
        value = None
        if 'default' in question:
            value = question['default']
        if 'line' in question:
            matching = [(q,a) for q, a in qas if question['line'] in q]
            if len(matching) > 1:
                print("Error: Configured question '{}' matches multiple questions in the form.".format(question['line']))
                sys.exit(1)
            elif len(matching) == 1:
                if matching[0][1] != "Not answered":
                    value = matching[0][1]
        if 'mapping' in question and value is not None:
            for item in conf['mappings'][question['mapping']]:
                if value.startswith(item['in']):
                    value = item['out']
                    break
            else: # If not break
                raise ValueError(
                        "Unable to map value '{}' for question '{}'.".format(
                                    value,
                                    question.get('line'))
                        )
        if 'transform' in question and value is not None:
            value = transforms[question['transform']](value)

        if value is not None and value is not '':
            udfs_to_set[question['udf']] = value
    
    if test:
        print(udfs_to_set)
    else:
        for uname, uvalue in udfs_to_set.items():
            process.udf[uname] = uvalue
        try:
            process.udf['Sample submission form imported'] = True
            process.put()
            print("Submission form imported successfully.")
        except requests.exceptions.HTTPError as e:
            print("Error while updating fields in LIMS: {}.".format(e))
            return 1
try:
    lims_process_id = sys.argv[1]
    test = len(sys.argv) > 2 and sys.argv[2] == "test"
except IndexError:
    print("Error: Invalid arguments specified.")
    print("usage:")
    print("nettskjema-importer.py LIMS_PROCESS_ID")
    print(" -- or --")
    print("nettskjema-importer.py INPUT_FILE test")
    sys.exit(1)

sys.exit(main(lims_process_id, test))
