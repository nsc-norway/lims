#!/bin/bash



echo "User passwords (Specified in the PreReqs document):"
echo " The users are created after installing the RPM, so we set them in the 30-... script."

sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
sudo yum install -y postgresql96-server git vim
sudo /usr/pgsql-9.6/bin/postgresql96-setup initdb

# Edit: /var/lib/pgsql/9.6/data/postgresql.conf
# Set correct size.
# SET shared_buffers = 6 GB

# Edit: /var/lib/pgsql/9.6/data/pg_hba.conf
# CHANGE "ident" to "md5"
### # IPv4 local connections:
### host    all             all             127.0.0.1/32            md5
### # IPv6 local connections:
### host    all             all             ::1/128                 md5

echo "Make sure the short host name is resolvable! The following should not have any dot:"
hostname -s

echo "If this doesn't work, then add it to the /etc/hosts file line with the IP address,"
echo "for example: 129.240.13.72   sandbox-lims.sequencing.uio.no sandbox-lims.sequencing sandbox-lims."

echo "Checking that I can ping the short hostname, if not, then fix as described above:"
echo ping -c 3 `hostname -s`
ping -c 3 `hostname -s` || (echo "Press enter to continue"; read)


sudo systemctl enable postgresql-9.6
sudo systemctl start postgresql-9.6

# Create database user
sudo -u postgres psql -c 'CREATE ROLE clarity WITH NOSUPERUSER CREATEDB NOCREATEROLE LOGIN;'

echo "Password for the PostgreSQL user clarity are saved in the admin git repo under"
echo "documentation/lims. Enter the database password to set now:"
sudo -u postgres psql -c '\password clarity'

# Create databases. If migrating from an old server, the database name of clarityDB should match
# the one on that server. Script 10 instructed you to make a note of the name ;)
sudo -u postgres createdb --owner clarity "clarityDB"

# Create the tenant lookup DB
sudo -u postgres createdb --owner clarity "clarityTenantLookup"

echo "TZ='Europe/Oslo'; export TZ" > /etc/profile.d/01_tz.sh

# Enable remote HTTP(S) access in firewall configuration
sudo firewall-cmd --zone=public --add-service=https
sudo firewall-cmd --zone=public --permanent --add-service=https
sudo firewall-cmd --zone=public --add-service=http
sudo firewall-cmd --zone=public --permanent --add-service=http

