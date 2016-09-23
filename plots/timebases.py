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

query = open("bases.sql").read()
cur.execute(query)

# Get list of dates and of per-run yield
dates, yields = zip(*cur)

cumyield = np.cumsum(yields)

plt.plot(dates, cumyield)
plt.savefig('bases.png')

