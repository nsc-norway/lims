
sudo yum --enablerepo=GLS_NovaSeq install BaseSpaceLIMS-sequencer-api

# Run this:
# Enter the following values:
# Use apiuser? = N
# Username for communication = novaseqapi
# Enter a dummy value for the novaseqapi password. We don't have it. See below.
# Accept default lifetime.
sudo -u glsjboss /opt/gls/clarity/config/configure_sequencer_api_application.sh

# Edit the application configuration file:
# * Enter the correct, encrypted novaseqapi password. Fetch it from an already configured server.
#   If we don't have it, then instead generate a new one when running the previous script.
# * Edit [novaseq.sequencingStepNames] so it matches the step name in the NovaSeq workflow;
#   currently "AUTOMATED - NovaSeq Run NSC 3.0"
sudo vim /opt/gls/clarity/extensions/sequencer-api/application.yml

# Restart clarity
sudo /opt/gls/clarity/bin/run_clarity.sh stop
sudo /opt/gls/clarity/bin/run_clarity.sh start
