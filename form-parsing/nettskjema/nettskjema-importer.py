import re
import sys
import yaml
import datetime


def get_read_length(value):
    """Extracts the read length without spaces"""
    m = re.match(r"(\d) x (\d+) bp", value)
    if m:
        return "{}x{}".format(m.group(1), m.group(2))
    else:
        return value

transforms = {
    'first_line':       lambda x: x.splitlines()[0],
    'get_read_length':  get_read_length,
    'skip_first_line':  lambda x: '\n'.join(x.splitlines()[1:]),
    'todays_date':      lambda x: datetime.date.today(),
    'yes_no_bool':      lambda x: True if x == "Yes" else False
}

mappings = {
    'delivery_method': [
        ('(non-sensitive data) Upload to our password protected delivery server.', 'Norstore'),
        ('(non-sensitive data) Upload to NeLS', 'NeLS project'),
        ('(sensitive data) Upload to TSD project', 'TSD project'),
        ('(sensitive data) Portable hard drive', 'HDD_PLACEHOLDER_STRING')
    ],
    'delivery_method2_hdd': [
        ('Your own portable hard drive',     'User HDD'),
        ('Purchase a portable hard drive',   'New HDD')
    ],
    'evaluation_type': [
        ('Yes',                 'QC only'),
        ('No',                  'Prep')
    ],
    'project_type': [
        ('Non-sensitive',       'Non-Sensitive'),
        ('Sensitive',           'Sensitive')
    ]
}


def main(input_file_name):
    with open('config.yaml') as conffile:
        conf = yaml.safe_load(conffile)
    with open(input_file_name) as input_file:
        lines = input_file.readlines()

    # First line of answers have a leading space with something
    # non-spacey after it
    answer_first_line_numbers = [
            i
            for i, l in enumerate(lines)
            if re.match(r" .*[^ ].*", l)
            ]
    
    # This preliminary stage just gets the full question and answer
    # texts
    qas = []
    for ans_start_line in answer_first_line_numbers:
            if ans_start_line == 0: continue # First line, nothing

            # Look behind for question text up to blank line
            q_start_line = ans_start_line - 1
            while q_start_line - 1 > 0 and lines[q_start_line - 1] != '\n':
                    q_start_line -= 1
            # Get question
            question = "\n".join(k.strip() for k in lines[q_start_line:ans_start_line])

            # Take lines until a blank line comes
            ans_end_line = ans_start_line
            while ans_end_line + 1 < len(lines) and lines[ans_end_line+1] != '\n':
                    ans_end_line += 1
            # Get answer
            answer = "\n".join(k.strip() for k in lines[ans_start_line:ans_end_line+1])
            # Remove hyperlink annotations made by docx2txt
            answer = re.sub(r" \[HYPERLINK: [^\]]+\]", "", answer)
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
            for mapping in mappings[question['mapping']]:
                if value.startswith(mapping[0]):
                    value = mapping[1]
                    break
            else: # If not break
                raise ValueError(
                        "Unable to map value '{}' for question '{}'.".format(
                                    value,
                                    question.get('line'))
                        )
        if 'transform' in question and value is not None:
            value = transforms[question['transform']](value)

        if value is not None:
            udfs_to_set[question['udf']] = value
    
    print(udfs_to_set)
    

main(sys.argv[1])