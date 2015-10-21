### LIMS Setup!

This monitoring system needs a custom UDF to track which processes
are "open". This is done to prevent the need to load all processes
for every request. It also requires the UDFs provided by Genologics
and the Slurm job UDFs (currently: Job status, Recently completed, 
Processing completed date). See other SETUP files.

Check out main.py. For each process type in the following arrays,
add a UDF as specified below:

SEQUENCING: process types in the second element of the tuples
DATA_PROCESSING: list of process types in second element of tuples

UDF specficiation:
Name: Monitor
Type: Check Box
[ ] Show field in tables
[X] Allow custom entries
[X] Use first preset as default
[ ] Users can enter values in GUI
Second tab: add preset: true


### System setup for proper deployment

Make a directory to hold the server-side code.
sudo mkdir /var/www/limsweb
copy the pipeline and genologics directories into limsweb. 
sudo chmod -R a+rX /var/www/limsweb
ls -l /var/www/limsweb
total 8
drwxr-xr-x. 8 root root 4096 May 26 11:17 genologics
drwxr-xr-x. 9 root root 4096 May 26 11:03 pipeline


Create a user to run the application, with access to the LIMS 
apiuser credentials. The reason for having a new user is that the
monitor application needs access to the API, but not the sequence
data. We don`t give the apache user lims access and don`t use the 
seq-user, as that has access to all NSC data.

sudo adduser -d /var/www/limsweb -r limsweb

Create a private directory to hold the credentials
sudo mkdir /var/www/limsweb/private
sudo vim /var/www/limsweb/private/password
(paste credentials, save)
sudo chown -R limsweb:limsweb /var/www/limsweb/private
sudo chmod 500 /var/www/limsweb/private
sudo chmod 400 /var/www/limsweb/private/password


Install the configuration:
Copy the configuration into /etc/httpd/conf.d/
sudo cp pipeline/monitor/sequencing-overview.conf /etc/httpd/conf.d/

The line in the configuration file:
WSGISocketPrefix /var/run/wsgi
is RHEL-specific, needed for the WSGI to be able to communicate with 
apache. Create this directory.


Allow httpd to make network connections:
sudo setsebool -P httpd_can_network_connect 1


