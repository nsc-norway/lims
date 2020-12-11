## Parsing Nettskjema Project Submission Form

Simple script to parse the result of the Nettskjema-based form, and
import it into LIMS. Based on a perl script docx2txt
(http://docx2txt.sourceforge.net/) bundled here in git.

The input is not directly from Nettskjema, but instead from a document
file created by pasting the content of the email we receive for each
submission (this procedure is used because we already keep a record of
projects in this way).


### Functional overview / Input requirements

The input file is a list of questions and answers. The text of the questions
is contained in a configuration file, used to map the questions to fields
in LIMS.

The responses from the user are identified by a leading space on the line.
For multi-line fields it's a bit more complex: docx2txt (which is the best
tool I could find) will only indent the first line of a multi-line response.

Using the leading spaces as guides, the parser will look at contiguous blocks
of text before and after the response. It scans the text before the line
for known question strings. It uses the text on the indented line and the
following lines as the answer, up to the next blank line.


### Configuration



