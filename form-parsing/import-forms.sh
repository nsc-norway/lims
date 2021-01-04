#!/bin/bash

set -e

# TODO if the old form type is ever completely removed:
# The "or" clause must be removed.
nsc-python3 /opt/gls/clarity/customextensions/lims/form-parsing/nettskjema/nettskjema-importer.py $1 \
    || nsc-python3 /opt/gls/clarity/customextensions/lims/form-parsing/read-submission-form.py $1
nsc-python27 /opt/gls/clarity/customextensions/lims/form-parsing/read-project-eval-form.py $1
