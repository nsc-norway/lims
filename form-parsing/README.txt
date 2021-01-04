# Parsing of forms

Scripts to run in the context of the Project Evaluation Step, to import information about these:

- Sample submission form (NSC Project Submission), filled by the user.
- Project Evaluation Form filled by NSC staff.

The process is driven by import-forms.sh, which takes the LIMS process ID as a parameter. See
the README file in nettskjema/ for details on parsing the new submission form, and how to
adapt to changes in the form.

When making changes to the custom fields (UDFs) of the project in LIMS, also take care to update
../Project_Evaluation_Step/settings.py, which defines a list of fields to copy between the 
Project Evaluation Step process and the project in LIMS.

