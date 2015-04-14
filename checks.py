import re

def is_valid_email(text):
    return re.match(r".*@.+\..+$", text)

