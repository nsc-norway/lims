import re
import sys

def main(input_file_name):
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
        q_a = []
        for ans_start_line in answer_first_line_numbers:
                if ans_start_line == 0: continue # First line, nothing

                # Look behind for question text up to blank line
                q_start_line = ans_start_line - 1
                while q_start_line - 1 > 0 and lines[q_start_line - 1] != '\n':
                        q_start_line -= 1
                # Get question and trim last \n
                question = "\n".join(k.strip() for k in lines[q_start_line:ans_start_line])

                # Take lines until a blank line comes
                ans_end_line = ans_start_line
                while ans_end_line + 1 < len(lines) and lines[ans_end_line+1] != '\n':
                        ans_end_line += 1
                # Get answer and trim last \n
                answer = "\n".join(k.strip() for k in lines[ans_start_line:ans_end_line+1])

                print (repr(answer))

main(sys.argv[1])