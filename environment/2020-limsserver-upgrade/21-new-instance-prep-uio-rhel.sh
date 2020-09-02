#!/bin/bash

sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
sudo yum install -y postgresql96-server git vim
sudo /usr/pgsql-9.6/bin/postgresql96-setup initdb
sudo systemctl enable postgresql-9.6
sudo systemctl start postgresql-9.6

# Edit: /var/lib/pgsql/9.6/data/postgresql.conf
# SET shared_buffers = 6 GB

# Edit: /var/lib/pgsql/9.6/data/pg_hba.conf
# CHANGE "ident" to "md5"
### # IPv4 local connections:
### host    all             all             127.0.0.1/32            md5
### # IPv6 local connections:
### host    all             all             ::1/128                 md5
