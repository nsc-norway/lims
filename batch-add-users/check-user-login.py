import requests


uri = 'https://ous-lims.sequencing.uio.no/api'
for username, password in [line.strip().split() for line in open("user_list.tsv").readlines()]:
    r = requests.get(uri, auth=(username, password))
    if r.status_code in [403, 200]:
        print (username, ": password accepted")
    elif r.status_code == 401:
        print (username, ": password rejected")
    else:
        print (username, ": unexpected status code", r.status_code)

