import re
import sys
import yaml

def get_evaluation_type

transforms = {
    'evaluation_type': None,
    'delivery_method': None,
    'first_line': None,
    'skip_first_line': None,
}

mappings = {
    'project_type': [
        ('Non-sensitive',       'Non-Sensitive'),
        ('Sensitive',           'Sensitive')
    ],
    'evaluation_type': [
        ('Yes',                 'QC only'),
        ('No',                  'Prep')
    ],
    'yes_no_bool': [
        ('Yes',                 True),
        ('No',                  False)
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
                value = matching[0][1]
        
        if value is not None:
            udfs_to_set[question['udf']] = value
    
    print(udfs_to_set)
    

main(sys.argv[1])