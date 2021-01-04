## Parsing Nettskjema Project Submission Form

Simple script to parse the result of the Nettskjema-based form, and
import it into LIMS. Based on a perl script docx2txt
(http://docx2txt.sourceforge.net/) bundled here in git.

The input is not directly from Nettskjema, but instead from a document
file created by pasting the content of the email we receive for each
submission (this procedure is used because we already keep a record of
projects in this way).

This script updates a step (process) in LIMS with the data from the
form, according to a configuration file.


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

The configuration file config.yaml contains a list of "UDF" (User Defined
Fields) definitions, also corresponding to questions in the form. The value
is called "questions" in the YAML file.

Each configuration item may contain the following. `udf` is required, all
other properties are optional:

*   `udf`: Name of the custom field (UDF) to set in LIMS.
*   `line`: Match a line in the question text.
*   `default`: Sets a default value. The UDF will be set to this value
    if there is no matching line. The default will also be processed with
    mappings and transformations (see below).
*   `transform`: Transform the output according to a function. 
    Transformations are defined in the python script.
*   `mapping`: Name of a mapping. Replaces certain input values with
    other output values. Mappings are defined in the config file.

The UDF will be included in the put request if and only if it has a
value: that means if there is a match for the line, and the question is 
answered, or if it has a default value.
