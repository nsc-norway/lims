from operator import itemgetter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
#plt.style.use('ggplot')
import numpy as np
import psycopg2
import socket


if socket.gethostname() == "dev-lims.sequencing.uio.no":
    user = "clarityLIMS"
else:
    user = "clarity"
conn = psycopg2.connect("dbname=clarityDB user={0}".format(user))
cur = conn.cursor()

query = open("exomes.sql").read()
cur.execute(query)

timeseries = enumerate(sorted(row[0] for row in cur))

# plot takes two lists, X and Y. This transposes the 
# result set, which is one list of (x,y) tuples.
# It also reverses the order, since we use the time 
# as x and the count as y.
x_y = reversed(zip(*timeseries))
plt.plot(*x_y)
plt.savefig('exomes.png')

