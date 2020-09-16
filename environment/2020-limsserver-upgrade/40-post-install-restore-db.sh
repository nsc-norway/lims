
# Install/Upgrade guide item
# 2. Restore backup

sudo -u postgres dropdb "clarityDB"
sudo -u postgres createdb -O clarity "clarityDB"
sudo chown postgres /opt/backup/opt/clarity-5.1-*.tar
sudo -u postgres ls /opt/backup/opt/clarity-5.1-*.tar

if [ ! sudo -u postgres pg_restore -Ft -d clarityDB /opt/backup/opt/clarity-5.1-*.tar ]
then
    echo "## Restore failure. Extract the tar file and run pg_restore with format 'd'"
    echo "## ... mkdir /big/place"
    echo "## ... cd /big/place"
    echo "## ... tar xf /opt/backup/opt/clarity-5.1-*.tar"
    echo "## ... sudo chown -R postgres ."
    echo "## ... sudo -u postgres pg_restore -Fd -d clarityDB ."
    echo -n "If running this as a script, you should do the above commands then press Enter."
    read
fi

sudo rsync -r /opt/backup/opt/gls/clarity/users/glsftp/ /opt/gls/clarity/users/glsftp/
sudo chown -R glsftp:claritylims /opt/gls/clarity/users/glsftp/

sudo rsync -rl /opt/backup/opt/gls/clarity/customextensions/ /opt/gls/clarity/customextensions/
sudo chown -R glsjboss:claritylims /opt/gls/clarity/customextensions

# Set permissions to make it easier for claritylims group to work
sudo chmod g+s /opt/gls/clarity/customextensions
sudo setfacl -d -m g::rwx /opt/gls/clarity/customextensions

# Skip restore content of:
# - /opt/gls/clarity/glscontents. We have nothing in it.
# - /etc/httpd/conf.d. Instead configure manually now...

# Set up certificate
# See also https://genologics.zendesk.com/hc/en-us/articles/360024942552
sudo mkdir /etc/httpd/sslcertificate
sudo rsync /opt/backup/etc/httpd/sslcertificate/*.* /etc/httpd/sslcertificate
sudo chmod -R go-rwx /etc/httpd/sslcertificate
sudo chown root /etc/httpd/sslcertificate
sudo ls -l /etc/httpd/sslcertificate

cd /opt/gls/clarity/config/

echo "Enter the paths to the certs in /etc/httpd/sslcertificate when asked"
echo "It will give an error that they are the same file, because we have already"
echo "restored them to the correct location, as per the instructions."
sudo bash installCertificates.sh

# Restore corntab
sudo cp /opt/backup/etc/crontab /etc/crontab

# Make sure we're here
cd /opt/gls/clarity/config/

# 5. Migrate the database to new clarity version
sudo -u glsjboss ./migrate_claritylims_database.sh

# 6. Install NGS package and preconfigured workflow
sudo yum --enablerepo=GLS_clarity52 install ClarityLIMS-NGS-Package-v5 BaseSpaceLIMS-Pre-configured-Workflows-Package

# Also install sequencer integration RPMs

# 7. Delete ElasticSearch indices
sudo service elasticsearch start
curl -XDELETE 'http://localhost:9200/_all'

sudo /opt/gls/clarity/bin/run_clarity.sh stop
sudo /opt/gls/clarity/bin/run_clarity.sh start

echo "After completing this procedure, perform the validation"
echo "Sequencer integrations are not installed by commands in this script. Determine the"
echo "appropriate sequencer integrations and install them manually."
