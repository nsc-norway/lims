# NSC lims repo -- Miscellaneous scripts for Clarity LIMS.

See wiki for operation procedures: https://github.com/nsc-norway/lims/wiki


## Overview

This repo contains a large number of stand-alone scripts, which are called by the 
External Program Plugin (EPP) interface of Clarity LIMS. There are also several
cron jobs and small web applications (see below).


Requirements:
  - Many scripts require the SciLife genologics library, or the NSC extended
    version. The genologics library itself requires "requests" (from pip or yum).

  - There are other requirements, including Word / Excel file interfaces, numpy,
    etc. In some cases it will be specified in comments in the script, and other
    scripts need to be updated to include this information (it is then possible 
    to determine the requirement by looking at import statements).


## Repo organisation

The code is located in directories depending on which broad topic it relates to.
A more systematic approach is the tree under the processtype/ directory: Each 
"process type" in LIMS may have a number of scripts (EPP) associated with it. In the 
processtype directory, there is a subdirectory for each process type, with links 
to the scripts used by that process type. This makes it easy to associate between
scripts and process types. There are some exceptions:

  - Helper scripts in helpers/ may be used directly, without a link, because they
    are used so frequently.
  - When the version of a process type is updated and no changes are made to the
    script configuration, it's not necessary to create a new directory and links.

Older process types do not follow this system, so a script may be in use even if
it has no links under processtype/.

Non-EPP scripts are either manually invoked scripts, cron jobs, or web applications.

  - Cron jobs: 
    - helpers/workflow-run-last-step.py
    - sequencing/sequencing-to-demultiplexing-cron.py
    - sequencing/auto-next-script.py
  - Web applications:
    - counter/ : The "base counter" is a publicity display showing the ongoing 
      sequencing by counting the number of bases that have been sequenced, based on 
      the local storage directory. This code does not use the LIMS at all.
    - monitor/ : This is the "Overview" page, showing ongoing sequencing runs which
      have been registered in LIMS.
    - proj_imp/ : The project importer is used to create standardised projects for
      "external" users who are not heavily involved in the LIMS.
  - Otter
    - deploy/ : Deployment scripts -- pushes the current git commit into production
    - tests/ : Unit tests. The number and quality of tests is currently limited.

## Directories

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
  - lot-tracker/ : Counting how many reactions used from lots
  - normalisation/ : Computations and support scripts for normalising the
    concentration of samples.
  - printout/ : System for printing tables, and scripts for specific kinds 
    of print jobs.
  - proj_imp/ : Web interface for quickly importing simple sequencing-only projects
  - Project_Evaluaton_Step/ : The project evaluation sysstem supports assigning
    UDFs to projects, and reading them back from projects to the process instance.
  - qpcr/ : Used for working with the qPCR machine.
  - reagents-ui/ : Web application and API proxy for reagent registration. Required
    by the reagent-scanning Java application (located in the reagent-scanning repo).
  - sample-prep/ : Anything related to sample prep
  - set-reagent-labels/ : Manipulate the "reagent labels" of groups of analytes.
    Reagent labels are the representations of index sequences in the LIMS.

