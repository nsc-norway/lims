### LIMS Setup!

This monitoring system needs a custom UDF to track which processes
are "open". This is done to prevent the need to load all processes
for every request. The UDF is a boolean called Monitor.

It also requires the UDFs provided by Genologics (Run ID) and the 
demultiplexing job UDFs (currently: Job status, Current job). Finally
it uses the tracking UDFs on Container, which keep track of recent 
runs: Recently completed, Processing completed date. 

Monitor UDF: For each process type in the SEQUENCING and 
DATA_PROCESSING arrays in main.py, add a UDF as specified below:

UDF specficiation:
Name: Monitor
Type: Check Box
[ ] Show field in tables
[X] Allow custom entries
[X] Use first preset as default
[ ] Users can enter values in GUI
Second tab: add preset: true


### System setup for proper deployment

<This subsystem used to have quite detailed installation instructions.
 When moving to the LIMS server, this should be updated.>

Install the configuration:
Copy the configuration into /etc/httpd/conf.d/
sudo cp pipeline/monitor/sequencing-overview.conf /etc/httpd/conf.d/

The line in the configuration file:
WSGISocketPrefix /var/run/wsgi
is RHEL-specific, needed for the WSGI to be able to communicate with 
apache. Create this directory.


Allow httpd to make network connections:
sudo setsebool -P httpd_can_network_connect 1


