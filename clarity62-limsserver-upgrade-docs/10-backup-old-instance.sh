#!/bin/bash


echo "MAKE SURE YOU HAVE A BACKUP OR SNAPSHOT OF THE LIMS SERVER"


# 1. Deploy LIMS scripts to production instance


# Run as the root user on the old clarity server before upgrade

# -- 1. validation ---
# The Pre-validation RPM for the new version should be installed here.
# (this is not usually the case, we have to add the repo file explicitly)
# Install PreValidation 5.2:
yum --enablerepo=GLS_clarity62-onprem install ClarityLIMS-UpgradePreValidation
bash /opt/gls/ClarityUpgradeValidation/bin/validate.sh
# VERIFY NO "ERROR" MESSAGES!
yum remove ClarityLIMS-UpgradePreValidation

# -- 2. Stop Clarity --
/opt/gls/clarity/bin/run_clarity.sh stop

# -- 3. --
# pg_dump doesn't seem to respect TMPDIR var. Instead we create /opt/tmp and bind-mount it for the
# duration of the database backup.
sudo -u postgres bash -c 'pg_dump -b -O clarityDB' | gzip > /dumping/clarity-6.2-`date +%Y%m%d%H%M`.sql.gz


cd /
rpm -qa | grep "BaseSpace\|Clarity" > clarityrpms.txt
tar cf /dumping/backups.tar \
    /opt/gls/clarity/users/glsftp \
    /opt/gls/clarity/customextensions \
    /opt/gls/clarity/glscontents \
    /etc/httpd/conf.d \
    /etc/httpd/sslcertificate \
    /etc/crontab \
    /var/lib/pgsql/9.6/data/pg_hba.conf \
    /var/lib/pgsql/9.6/data/postgresql.conf \
    clarityrpms.txt \
    /root/ssl/$HOSTNAME.cnf

echo "Todo: copy postgres backup and file backup."
