import tempfile
import subprocess
import os
import re
import shutil

HEADER=os.path.dirname(os.path.realpath(__file__)) + "/head.tex"
FOOTER=os.path.dirname(os.path.realpath(__file__)) + "/foot.tex"
PRINTER="samsung-laser"

def tex_escape(s):
    return re.sub(r"[^\d:a-zA-Z()+-. ]", lambda x: '\\' + x.group(0), s)

def print_table(title, data, table_header=True): 
    """Accepts a list of lists as data, the first row is treated as a header"""

    tmpdir = tempfile.mkdtemp()
    with open(tmpdir + "/table.tex", "w") as texfile:
        hdata = open(HEADER).read()
        texfile.write(hdata.replace("__TITLE__", tex_escape(title)))
        ncols = len(data[0])
        if table_header:
            texfile.write(" & ".join(["{\\bf " + tex_escape(c) + "}" for c in data[0]]) + " \\\\\n")
            texfile.write("\\midrule\n")
            body = data[1:]
        else:
            body = data

        for row in body:
            texfile.write(" & ".join([tex_escape(c) for c in row]) + " \\\\\n")

        texfile.write(open(FOOTER).read())

    DEVNULL = open(os.devnull, 'wb') # discard output, pdflatex too verbose
    subprocess.check_call(["pdflatex", "table.tex"], cwd=tmpdir, stdout=DEVNULL)
    subprocess.check_call(["lp", "-d", PRINTER, tmpdir+"/table.pdf"], stdout=DEVNULL)

    shutil.rmtree(tmpdir)

