#!/bin/bash

yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
yum install -y postgresql96-server git vim
#/usr/pgsql-9.6/bin/postgresql96-setup initdb
#systemctl enable postgresql-9.6
#systemctl start postgresql-9.6
