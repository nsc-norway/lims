# Clarity 6.2 upgrade procedure / notes

This files in this directory describe the Clarity LIMS upgrade procedure installation procedure.
Any configuration that can be automated is performed using ansible. All commands should be listed
in the .sh files, but note that other actions may be necessary and are also described in the .sh
files.

Procedure outline:

* Back up the old instance
* Perform a clean install on a new host
* Restore old database and files
* Testing

The procedure may also be relevant for a complete clean install.


## Official documentation

Technical requirements: https://support-docs.illumina.com/SW/ClarityCore_v6/Content/SW/ClarityLIMS/Installation/Upgrade_OP2OP_42-61-Oracle-43-52_swCL_v62.htm

Pre-Install Requirements: https://support-docs.illumina.com/SW/ClarityCore_v6/Content/SW/ClarityLIMS/Installation/Upgrade_OP2OP_42-61-Oracle-43-52_swCL_v62.htm

Upgrade procedure: https://support-docs.illumina.com/SW/ClarityCore_v6/Content/SW/ClarityLIMS/Installation/Upgrade_OP2OP_42-61-Oracle-43-52_swCL_v62.htm

Main Install procedure: https://support-docs.illumina.com/SW/ClarityCore_v6/Content/SW/ClarityLIMS/Installation/Installation_Procedure_swCL_v62.htm




### OUS node: Create principals view

The following view to grant access to principals without password column. Run in psql as
postgres user: (TODO confirm)

    sudo -u postgres psql -c 'CREATE OR REPLACE VIEW principalsview AS SELECT principalid, username, isvisible, isloggedin, datastoreid, ownerid, isglobal, createddate, lastmodifieddate, lastmodifiedby, accountlocked, researcherid, locked, hasloggedin FROM principals;' clarityDB



## General information

After completion, remove /opt/restore and the backup tar files.
