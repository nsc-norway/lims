#!/bin/sh

set -e

/usr/bin/python /opt/gls/clarity/customextensions/lims/form-parsing/read-submission-form.py $1
/usr/bin/python /opt/gls/clarity/customextensions/lims/form-parsing/read-project-eval-form.py $1

