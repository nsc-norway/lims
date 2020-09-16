#!/bin/bash

# Run as the root user on the old clarity server before upgrade


# -- 1. validation ---

# The Pre-validation RPM for the new version should be installed here.
# (this is not usually the case, we have to add the repo file explicitly)
# Install PreValidation 5.2:
yum --enablerepo=GLS_clarity52 install ClarityLIMS-UpgradePreValidation
bash /opt/gls/ClarityUpgradeValidation/bin/validate.sh
yum remove ClarityLIMS-UpgradePreValidation


/opt/gls/clarity/bin/run_clarity.sh stop

# pg_dump doesn't seem to respect TMPDIR var. Instead we create /opt/tmp and bind-mount it for the
# duration of the database backup.
mkdir -p /opt/tmp
chown postgres:postgres /opt/tmp
chmod 2700 /opt/tmp
mount -o bind /opt/tmp /tmp
sudo -u postgres bash -c 'pg_dump -b -O -Ft clarityDB' | gzip > /opt/clarity-5.1-`date +%Y%m%d%H%M`.tar
umount /tmp

cd /
rpm -qa | grep "BaseSpace\|Clarity" > clarityrpms.txt
tar cfJ /opt/backups.tar.xz \
    /opt/gls/clarity/users/glsftp \
    /opt/gls/clarity/customextensions \
    /opt/gls/clarity/glscontents \
    /etc/httpd/conf.d \
    /etc/httpd/sslcertificate \
    /etc/crontab \
    /var/lib/pgsql/9.6/data/pg_hba.conf \
    /var/lib/pgsql/9.6/data/postgresql.conf \
    clarityrpms.txt \
    /opt/clarity-5.1-*.tar
