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
  - helpers/ : small scripts with general utility.
  - label-printing/ : Printing labels directly from the LIMS. The EPP
    (LIMS) script only writes files in ODF format to a directory, and a 
    separate daemon script initiates the print jobs.
  - normalisation/ : Computations and support scripts for normalising the
    concentration of samples.
  - printout/ : System for printing tables, and scripts for specific kinds 
    of print jobs.
  - Project_Evaluaton_Step/ : The project evaluation sysstem supports assigning
    UDFs to projects, and reading them back from projects to the process instance.
  - qpcr/ : Used for working with the qPCR machine.
  - set-reagent-labels/ : Manipulate the "reagent labels" of groups of analytes.
    Reagent labels are the representations of index sequences in the LIMS.
