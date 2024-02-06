# Install procedure script.
# While this is a .sh file, it's not necessarily meant to be run as a script.
# Recommended: reaad the file and execute the commands one by one.

echo Enter Postgres password for the Clarity user.
echo https://gitlab.ous.nsc.local/nsc-admin/secrets/-/blob/master/clarity-passwords.txt
sudo -u postgres psql -c '\password clarity'

# Check SELinux is disabled
echo -n "## SELinux state: "
getenforce

# Install main Clarity LIMS app.
sudo yum --enablerepo=GLS_clarity62-onprem install ClarityLIMS-App


# OUTPUT (no action needed here)

##         Please configure Clarity LIMS: As the glsjboss user, run the following configuration scripts found in /opt/gls/clarity/config/pending.
## 05_configure_claritylims_secretutil.sh
## 20_configure_claritylims_platform.sh
## 26_initialize_claritylims_tenant.sh
## 31_configure_claritylims_mixpanel.sh
## 
##         Please configure Clarity LIMS: As the root user, run the following configuration scripts found in /opt/gls/clarity/config/pending.
## 32_root_configure_rabbitmq.sh
## 40_root_install_proxy.sh


# Set local users passwords
echo "## See original installation record documents for the correct passwords to set and"
sudo passwd glsai
sudo passwd glsftp
sudo passwd glsjboss


##############################################################
# Configuration scripts in /opt/gls/clarity/config/pending/  #
##############################################################

# The database-related actions of these scripts will be eliminated when we restore the DBs
# in the next installation step. However, we complete all the step to make sure the file-based
# actions are completed.


# 05_configure_claritylims_secretutil.sh
echo "Values are given in the comments"

sudo -u glsjboss /opt/gls/clarity/config/pending/05_configure_claritylims_secretutil.sh

##Enter required value for Secret Util Mode <vault|file> [vault] :file
##
## Enter password value for app.ftp.password:
# From installation record
#
## Enter password value for app.ldap.managerPass:
# Blank
#
## Enter password value for app.rabbitmq.password:
# From Gitlab RabbitMQ password (see top of this file)
#
## Enter password value for db.tenant.password:
# From Gitlab PostgreSQL PW (see above)
#
## Enter password value for db.clarity.password:
# From Gitlab PostgreSQL PW (see above)
#
## Enter password value for db.lablink.password:
# From Gitlab PostgreSQL PW (see above)
#
## Enter password value for db.reporting.password:
# From Gitlab PostgreSQL PW (see above)
#
## Enter required value for Username of API user [apiuser] :
# Default (apiuser) 
#
## Enter password value for API user:
#  From installation record pdf

#20_configure_claritylims_platform.sh
echo "## See the installation record for what to enter:"
echo " - Use database type Postgres and database host FQDN: dev-lims.sequencing.uio.no (etc)."
echo " - USE THESE VALUES: The tenant lookup database is always 'clarityTenantLookup'"
echo "   and the DB username is always 'clarity'  (regardless of the installation record)"
sudo -u glsjboss /opt/gls/clarity/config/pending/20_configure_claritylims_platform.sh

#26_initialize_claritylims_tenant.sh
echo "## Running tenant init script."
echo " - The database name should always be clarityDB"
echo " - DB username is 'clarity'"
echo " - Admin and API users: enter values from installation record pdf."
echo " - Accept defaults for file server settings"
sudo -u glsjboss /opt/gls/clarity/config/pending/26_initialize_claritylims_tenant.sh


sudo /opt/gls/clarity/config/pending/32_root_configure_rabbitmq.sh


echo "## The certificate config will fail, we fix later"
sudo /opt/gls/clarity/config/pending/40_root_install_proxy.sh


echo "## Configure tomcat memory -- set JAVA_MAX_RAM to 8192. Pess Enter to open vim."
read
sudo vim /opt/gls/clarity/tomcat/current/bin/setenv.sh

