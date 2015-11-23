import psycopg2
import sys
import socket


try:
    project = sys.argv[1]
except IndexError:
    print "Use: python " + sys.argv[0] + " PROJECT_NAME"
    sys.exit(1)

if socket.gethostname() == "dev-lims.ous.nsc.local":
    user = "clarityLIMS"
else:
    user = "clarity"

conn = psycopg2.connect("dbname=clarityDB user={0}".format(user))
cur = conn.cursor()

query = open("query.sql").read()
cur.execute(query, (project,));
format_string = "%36s %5s %20s %5s"
print format_string % ("Run ID", "Lane", "Sample/pool", "QC")

total, ok = 0, 0
for row in cur:
    print format_string % row[0:4]
    total += 1
    if row[3] == "PASS":
        ok += 1

print ""
print "Project", project, "sequenced (or sequencing) on:"
print ""
print " TOTAL:   %3d lanes" % (total)
print " QC PASS: %3d lanes" % (ok)
print ""

cur.close()
conn.close()

