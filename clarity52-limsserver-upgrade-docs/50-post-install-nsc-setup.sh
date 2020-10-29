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
# Also set permissions for group claritylims, used by wsgi
sudo chgrp -R claritylims /opt/gls/clarity/customextensions
sudo chmod g+s /opt/gls/clarity/customextensions
sudo chmod -R g+rwX /opt/gls/clarity/customextensions

# Copy WSGI configuration files to httpd's configuration dir
sudo cp /opt/gls/clarity/customextensions/lims/monitor/sequencing-overview.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/sav-downloader/sav-downloader.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/reagents-ui/reagents.conf /etc/httpd/conf.d/
sudo cp /opt/gls/clarity/customextensions/lims/proj-imp/project-importer.conf /etc/httpd/conf.d/


# Mini-databases
# Reagent kit information
sudo mkdir /var/db/kits
sudo cp /opt/gls/clarity/customextensions/lims/reagents-ui/backend/kits.yml /var/db/kits
sudo chown -R glsai:claritylims /var/db/kits
