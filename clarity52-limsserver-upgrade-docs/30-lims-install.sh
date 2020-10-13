# Install procedure script.
# While this is a .sh file, it's not necessarily meant to be run as a script.
# Recommended: reaad the file and execute the commands one by one.


# Check SELinux is disabled
echo -n "## SELinux state: "
getenforce

# Find packages to install. ClarityLIMS-App will pull in the other ones as dependencies (check).
# Need to disable EPEL, otherwise we get wrong erlang version and a conflict.
cat /opt/backup/clarityrpms.txt
sudo yum --enablerepo=GLS_clarity52 --disablerepo=epel install ClarityLIMS-App

# OUTPUT

##         Please configure Clarity LIMS: As the glsjboss user, run the following configuration scripts found in /opt/gls/clarity/config/pending.
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

echo "## See the installation record for what to enter:"
echo " - Use database type postgresql and database host localhost."
echo " - EXCEPTION: The DB username is always 'clarity' and the tenant lookup database"
echo "   is always 'clarityTenantLookup'"
echo " - The password for the 'clarity' user is stored in a text file (same as was set"
echo "   in the perp (20) stage)."
sudo -u glsjboss /opt/gls/clarity/config/pending/20_configure_claritylims_platform.sh

echo "## Running tenant init script."
echo " - The database name should always be clarityDB"
echo " - Enter the same DB password as before."
echo " - Enter some values for the admin/facility/apiuser PWs -- they will be replaced when restoring the DB"
echo " - Accept defaults for file server settings"
echo " - Enter glsftp password for file server password"

sudo -u glsjboss /opt/gls/clarity/config/pending/26_initialize_claritylims_tenant.sh

sudo /opt/gls/clarity/config/pending/32_root_configure_rabbitmq.sh

echo "## The certificate config will fail, we fix later"
sudo /opt/gls/clarity/config/pending/40_root_install_proxy.sh
