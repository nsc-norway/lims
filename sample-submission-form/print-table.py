from docx import Document

d = Document("/home/fa2k/Downloads/sample-submission-form-(illumina)-2.docx")

for row in d.tables[0].rows:
   print " | ".join(c.text for c in row.cells)
   print " ------- "

