import requests
import time

password = open("password.txt").read().strip()

num_requests = 100
response_with_udf = ""
response_without_udf = ""
missing_list = []
for i in range(num_requests):
    r = requests.get("https://ous-lims.sequencing.uio.no/api/v2/processes/24-239912",
    #r = requests.get("https://ous-lims.sequencing.uio.no/api/v2/processes/24-239729",
                auth=('paalmbj', password))
    data = r.text
    # Check if it has the correct value for the Run ID UDF:
    if  '191204_NB501273_0258_AHF3H2BGXC' in data:
        response_with_udf = data
    else:
        missing_list.append(i)
        response_without_udf = data
    time.sleep(0.1)
print "Missing the Run ID UDF:", len(missing_list), "of", num_requests, ":", missing_list
open("response_with_udf.txt", "w").write(response_with_udf)
open("response_without_udf.txt", "w").write(response_without_udf)
