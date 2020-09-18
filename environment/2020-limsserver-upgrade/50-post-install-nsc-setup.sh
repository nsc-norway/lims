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
# 1. SAV downloader
cp /opt/gls/clarity/customextensions/....... /etc/httpd/conf.d/
