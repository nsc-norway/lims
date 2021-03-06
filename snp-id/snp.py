import sys
import csv
import re
import StringIO
from genologics.lims import *
from genologics import config

# -- PROBABLY NO LONGER USED (2017-01) --
# Was used on Sample Normalization step, check and discard if appropriate.

# This is a CSV file generator, for use with the Biomek robots.
# Various output formats are supported, see the filecfg parameter.

def sort_key(elem):
    input, output = elem
    container, well = output.location
    row, col = well.split(":")
    return (container, int(col), row)


def main(process_id, filecfg, file_id):
    lims = Lims(config.BASEURI, config.USERNAME, config.PASSWORD)
    process = Process(lims, id=process_id)

    out_buf = StringIO.StringIO()

    inputs = []
    outputs = []
    for i,o in process.input_output_maps:
        output = o['uri']
        if o and o['output-type'] == 'Analyte' and o['output-generation-type'] == 'PerInput':
            input = i['uri']
            inputs.append(input)
            outputs.append(output)

    lims.get_batch(inputs + outputs)
    
    rows = []
    header = []
    i_o = zip(inputs, outputs)

    if len(i_o) > 24:
        print "Too many samples for Biomek. Only 24 samples are supported. Skipping biomek files."
        sys.exit(0)

    for index, (input, output) in enumerate(sorted(i_o, key=sort_key)):
        sample_name = input.name.encode('utf-8')

        row_384 = [c for c in 'ABCDEFGHIJKLMNOP']
        row = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        well = "%s%d" % (row[index % 8], (index // 8) + 1)

        sample_no = re.match(r"([A-Za-z0-9]+)-", sample_name)
        sample_no = sample_no.group(1) if sample_no else sample_name
        if filecfg == "biomek1":
            filename = "biomek-snp1.csv"
            columns = [
                    ("Mastermiks_deckpos", "Mastermiks"),
                    ("TaqmanMM_Bronn", 2),
                    ("TaqmanMM_vol", 45),
                    ("EB-MM_Bronn", 1),
                    ("EB-MM_vol", 42),
                    ("Destinasjon_1_deckpos", "96_DNA_MM"),
                    ("96_DNA_MM_bronn1", well),
                    ("Provenummer", sample_no),
                    ("Rack_DeckPos_DNAror", "DNA_1"),
                    ("Pos_i_rack_DNA", index+1),
                    ("DNA_vol", 3)
                ]
            rows.append([x[1] for x in columns])

        elif filecfg == "biomek2":
            filename = "biomek-snp2.csv"

            # write 16 rows per sample
            for j in range(0, 16):
                columns = [
                        ("Provenummer", sample_no),

                        ("96_DNA_MM_deckpos", "96_DNA_MM"),
                        ("96_DNA_MM_bronn", well),

                        ("DNA_MM_vol", 5),
                        ("384plate_deckpos", "384_plate_1"),

                        ("384plate_bronn", "%s%02d" % (row_384[j],index+1)),
                    ]
                rows.append([x[1] for x in columns])

        if not header:
            header = [x[0] for x in columns]

    out_buffer = StringIO.StringIO()
    out = csv.writer(out_buffer)
    out.writerow(header)
    out.writerows(rows)

    outfile = Artifact(lims, id=file_id)
    gs = lims.glsstorage(outfile, filename)
    file_obj = gs.post()
    file_obj.upload(out_buffer.getvalue())


# Use:  PROCESS_ID CONFIG={"norm1"|"norm2"} OUTPUT_FILE_ID
main(sys.argv[1], sys.argv[2], sys.argv[3])

