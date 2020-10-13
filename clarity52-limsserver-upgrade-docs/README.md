# Clarity 5.2 upgrade procedure / notes

This is the main location of the installation procedure.

* For the servers on the UiO network, most of the commands are documented here.
* For servers on the NSC network, most of the setup is performed using Ansible.

The scripts and text files are numbered in order of application.

These commands are prepared for the upgrade to 5.2, which involves the following steps:

* Back up the old instance
* Clean install on a new host
* Restore old contents

The procedure may also be relevant for a complete clean install.


## Official documentation

Main procedure: Install/Upgrade: https://genologics.zendesk.com/hc/en-us/articles/360025478471-BaseSpace-Clarity-LIMS-Installation-Upgrade-Procedure

Technical requirements: https://genologics.zendesk.com/hc/en-us/articles/360025240471-Clarity-LIMS-Technical-Overview


## Decommissioning and preparation

### 10. Check and back up old instance: 10-postpare-old-instance.sh

After running / examining this script, transfer the backup to the new instance.


## 20. Preparing the new instance

Pre-installation requirements: https://genologics.zendesk.com/hc/en-us/articles/360024942472

The text file 20-new-instance-spec-requirements.txt specified the necessary tasks.

### Scripts used on sandbox / CEES LIMS:

First run:

* 21-sandbox-lims.sh: Specific to sandbox-lims.sequencing.uio.no
* 21-cees-lims.sh: Specific to cees-lims.sequencing.uio.no (TODO)

Then run the general preparation script.

* 22-new-instance-prep-uio-rhel.sh: Concrete commands used to configure the new instance.


### OUS network nodes -- Before Ansible

Set up the partitions for /opt and /var.

    # mkfs /dev/sdb
    # mkdir /mnt/new
    # mount /dev/sdb /mnt/new
    # cp -apx /var/* /mnt/new
    # mv /var /var.old
    # umount /mnt/new

If /opt has something in it, repeat the same procedure for /opt and /dev/sdc instead of
/var and /dev/sdb. Delete /mnt/new. Add entries into fstab.

Add to /etc/fstab:

    /dev/sdb	/var	ext4	defaults	0 0
    /dev/sdc	/opt	ext4	defaults	0 0

Mark the filesystems to be relabeled by SELinux. If you have already run ansible and thus
disabled SELinux, then this is not possible nor necessary.

    # touch {/,/var,/opt}/.autorelabel

Reboot. Remove /var.old if all is okay. Check df.

### OUS network nodes part 2

After applying the ansible role, set the password for the clarity DB user:

    sudo -u postgres psql -c '\password clarity'

The DB password is stored in the nscadmin repo.

Also set the password for the diagnostics database access user diagprod. This password is not
stored anywhere after the install (by NSC), so if you have to set this, use a new randomly
generated password and inform them.

    sudo -u postgres psql -c '\password diagprod'

The ansible roles for limsservers are then enough to make the servers ready for the next
step.


## 30. Installation and validation

Now the host should have its intended final hostname. Change the hostname and IP address now if
required. The script expects that the backup contents have been unpacked in `/opt/backup`.

Add an entry for the local server in /etc/hosts (re-run ansible site.yml on OUS network). On
UiO net, add the short one-component hostname to the line with the local server. It will only
have something like `cees-lims.sequencing`, not `cees-lims`. The short name should be the
last on the line.

The installation process is too interactive to automate with ansible. The commands in
`30-lims-install.sh` can be used to perform the installation on both UiO and OUS sites.


## 40. Restore and initialise

Follow the script `40-restore-db-and-configure.sh`, but it is recommended to enter the
commands manually one by one, and adapt any as necessary.

This script also installs the generally available add-ons: Pre-configured workflow package
and NGS package.



### OUS node: Set permissions to make it easier for multiple users to work

After performing the restore operation, set default full permissions for the limsdev group.

Set both default (-d) permissions and  

    sudo setfacl -R -d -m g:lims-dev:rwx /opt/gls/clarity/customextensions
    sudo setfacl -R -m g:lims-dev:rwx /opt/gls/clarity/customextensions


## 50. Post-install configuration

Validate that the LIMS works and all the data are there. Then delete /opt/backup. Cleanup temp hostname
from /etc/hosts if present.

### OUS node: Create principals view

The following view to grant access to principals without password column. Run in psql as
postgres user:

    sudo -u postgres psql -c 'CREATE OR REPLACE VIEW principals_ AS SELECT principalid, username, isvisible, isloggedin, datastoreid, ownerid, isglobal, createddate, lastmodifieddate, lastmodifiedby, accountlocked, researcherid, locked, hasloggedin FROM principals;'


## 60. Install optional components


## General information

