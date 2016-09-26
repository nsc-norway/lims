from operator import itemgetter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict
import numpy as np
import psycopg2
import socket
import os


if socket.gethostname() == "dev-lims.sequencing.uio.no":
    user = "clarityLIMS"
else:
    user = "clarity"
conn = psycopg2.connect("dbname=clarityDB user={0}".format(user))
cur = conn.cursor()

query = open(os.path.join(os.path.dirname(__file__), "bases.sql")).read()
cur.execute(query)

ptype_total = defaultdict(int)
ptype_values = defaultdict(list)

for row in cur:
    daterun, yiel, typ = row
    ptype_total[typ] += yiel
    ptype_values[typ].append((daterun, ptype_total[typ]))

for ptype in sorted(ptype_total.keys()):
    plt.plot(zip(*ptype_values[ptype]))

plt.savefig('bases.png')
