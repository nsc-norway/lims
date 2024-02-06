# Install/Upgrade guide item

# 2. Restore backup

sudo -u postgres dropdb "clarityDB"
sudo -u postgres createdb -O clarity "clarityDB"
sudo chown postgres /opt/backup/opt/clarity-5.1-*.tar
sudo -u postgres ls /opt/backup/opt/clarity-5.1-*.tar

# If running this script line by line (recommended), then perform the "sudo .......tar"
# command and see if it works, or see the echo statements if it fails.
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

# Restore file store
sudo rsync -r /opt/backup/opt/gls/clarity/users/glsftp/ /opt/gls/clarity/users/glsftp/
sudo chown -R glsftp:claritylims /opt/gls/clarity/users/glsftp/

# Restore custom scripts
sudo rsync -rl /opt/backup/opt/gls/clarity/customextensions/ /opt/gls/clarity/customextensions/
sudo chown -R glsjboss:claritylims /opt/gls/clarity/customextensions

# Skip restore content of:
# - /opt/gls/clarity/glscontents. We have nothing in it.
# - /etc/httpd/conf.d. Instead configure manually now...

# Set up certificate
# See also https://genologics.zendesk.com/hc/en-us/articles/360024942552
sudo mkdir /etc/httpd/sslcertificate
sudo rsync /opt/backup/etc/httpd/sslcertificate/*.* /etc/httpd/sslcertificate
sudo chmod -R go-rwx /etc/httpd/sslcertificate
sudo chown -R root /etc/httpd/sslcertificate
sudo ls -l /etc/httpd/sslcertificate

echo "Enter the paths to the certs in /etc/httpd/sslcertificate when asked"
echo "It will give an error that they are the same file, because we have already"
echo "restored them to the correct location, as per the instructions."
sudo bash /opt/gls/clarity/config/installCertificates.sh

# Restore corntab if applicable
sudo cp /opt/backup/etc/crontab /etc/crontab

# 5. Migrate the database to new clarity version
sudo -u glsjboss /opt/gls/clarity/config/migrate_claritylims_database.sh

# 6. Install NGS package and preconfigured workflow
sudo yum --enablerepo=GLS_clarity52 install ClarityLIMS-NGS-Package-v5 BaseSpaceLIMS-Pre-configured-Workflows-Package

# 7. Delete ElasticSearch indices
sudo service elasticsearch start
curl -XDELETE 'http://localhost:9200/_all'

sudo /opt/gls/clarity/bin/run_clarity.sh stop
sudo /opt/gls/clarity/bin/run_clarity.sh start

echo "After completing this procedure, perform the validation"
echo "Sequencer integrations are not installed by commands in this script. Determine the"
echo "appropriate sequencer integrations and install them manually."
