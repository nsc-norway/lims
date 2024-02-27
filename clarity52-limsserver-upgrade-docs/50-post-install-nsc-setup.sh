# Setup of custom LIMS features

# -- general --
echo "Enter the API user credentials for use by client library running as glsai."
echo "[genologics]" > /opt/gls/clarity/users/glsai/.genologicsrc
echo -n "LIMS server URL (e.g. https://sandbox-lims.sequencing.uio.no): "
read URL
echo "BASEURI=$URL" >> /opt/gls/clarity/users/glsai/.genologicsrc
echo "USERNAME=apiuser" >> /opt/gls/clarity/users/glsai/.genologicsrc
echo -n "API user PW: "
read PASSWORD
echo "PASSWORD=$PASSWORD" >> /opt/gls/clarity/users/glsai/.genologicsrc


# -- web apps --

# Allow the web server to read the custom scripts locations in clarity
sudo setfacl -R -d -m u:apache:rx /opt/gls/clarity/customextensions
sudo setfacl -R -m u:apache:rx /opt/gls/clarity/customextensions
sudo setfacl -R -d -m g:claritylims:rx /opt/gls/clarity/customextensions
# Also set permissions for group claritylims, used by wsgi
sudo chgrp -R claritylims /opt/gls/clarity/customextensions
sudo chmod g+s /opt/gls/clarity/customextensions
sudo chmod -R g+rwX /opt/gls/clarity/customextensions

# Copy WSGI configuration files to httpd's configuration dir
sudo cp /opt/gls/clarity/customextensions/lims/monitor/sequencing-overview.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/sav-downloader/sav-downloader.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/reagents-ui/reagents.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/proj-imp/project-importer.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/base-counter/counter.conf /etc/httpd/conf.d/

# Mini-databases
# Reagent kit information
sudo mkdir /var/db/kits
sudo cp /opt/gls/clarity/customextensions/lims/reagents-ui/backend/kits.yml /var/db/kits
sudo chown -R glsai:claritylims /var/db/kits

sudo mkdir /var/db/rundb
sudo chown -R glsai:claritylims /var/db/rundb

sudo mkdir /var/db/nsc-status
sudo chown -R glsai:claritylims /var/db/nsc-status

# Automation worker on LIMS-PC6

#1. Automation worker:

#Install procedure here:
# https://support-docs.illumina.com/SW/ClarityCore_v6/Content/SW/ClarityLIMS/AutomationWorkerNodes_swCL.htm


# Copy the deployment file
sudo cp /opt/gls/clarity/config/.templates/automation_worker/claritylims-aiinstaller-8.16.0.601-deployment-bundle.zip /data/runScratch.boston/
# This file can be decompressed in C:\TEMP to use for installation
# Run the SETUP_VISTA.bat as administrator.
# Enter usernames for apiuser and glsftp. Channel is limspc6.
# NOTE: The upper/lower case of apiuser must be the same as in the following secretutil command below.

# SecretUtil is needed.
# 1. Copy the secretutil jar file and config files
sudo cp -r  /opt/gls/clarity/tools/secretutil /boston/runScratch/UserData/paalmbj/

# 2. Remove the contents of secret.properties leaving an empty file

# 3. Per the guide, copy the secretutil directory to C:\opt\gls\clarity\tools\secretutil

# 4. Go to the system settings and set environment variabltes:

CLARITYSECRET_HOME=C:\opt\gls\clarity\tools\secretutil
CLARITYSECRET_ENCRYPTION_KEY= (generate a random password)

# 5. On elevated command prompt enter these

# REPLACE <secret> with the relevant passwords
java -jar C:\opt\gls\clarity\tools\secretutil\secretutil.jar -u=<secret> app.ftp.password
java -jar C:\opt\gls\clarity\tools\secretutil\secretutil.jar -u=<secret> -n=integration apiusers/apiuser


# Restart the service / reboot

