import psycopg2
import sys
import socket


try:
    project = sys.argv[1]
except IndexError:
    print "Use: python " + sys.argv[0] + " PROJECT_NAME"
    sys.exit(1)

if socket.gethostname() == "dev-lims.sequencing.uio.no":
    user = "clarityLIMS"
else:
    user = "clarity"

conn = psycopg2.connect("dbname=clarityDB user={0}".format(user))
cur = conn.cursor()

query = open("query.sql").read()
cur.execute(query, (project,));
format_string = "%s\t%s"

print format_string % ("Sample", "Reads")

for row in cur:
    print format_string % row[0:2]

cur.close()
conn.close()

