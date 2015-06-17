# lims
Miscellaneous scripts for Clarity LIMS.

See wiki for operation procedures: https://github.com/nsc-norway/lims/wiki

Requirements:
  - Many scripts require the SciLife genologics library, or the NSC extended
    version.

Code overview:

  - aggregate-qc/ : scripts for general QC procedures. `set-user-measurements.py`
    is run on any step to emulate a simple version of Aggregate QC. The other 
    scripts are designed to run on the Aggregate QC step itself.
  - archive-reagents/ : simple scripts to set the reagent lot state to ARCHIVED.
    Different script for different process type (HiSeq exceptions).
  - batch-add-users/ : adding multiple users from CSV file.
  - deploy/ : deployment scripts.
  - genologics : (link to genologics library, needs to be in parent dir.)
