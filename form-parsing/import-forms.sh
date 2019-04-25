#!/bin/sh

set -e

nsc-python35 /opt/gls/clarity/customextensions/lims/form-parsing/read-submission-form.py $1
/usr/bin/python /opt/gls/clarity/customextensions/lims/form-parsing/read-project-eval-form.py $1

