
# NEXTSEQ INTEGRATION

# It is not necessary to configure the properties again!
# Check the status:
sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar export | grep nextseq.v2



# 1.	Install NextSeq package:
sudo yum --enablerepo=GLS_Clarity_NextSeq install ClarityLIMS-Illumina-NextSeq-Package-v2

### -- begin section not necessary to do when re-installing ---

#sudo -u glsjboss /opt/gls/clarity/config/configure_extensions_nextseq_sequencingservice-v2.sh


# 2. Add property for the process name
#sudo -u glsjboss /opt/gls/clarity/bin/java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar addPropertyType nextseq.v2.seqservice.sequenceProcessBaseName "NextSeq 500/550 Run" "Sequencing process type base display name for partial term matching."

# 3. Set properties
#HOST=`hostname -f`
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.eventFileDirectory.1 '/boston/runScratch/gls_events_neseq'
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.eventFileDirectorySuffixes '1'
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.netPathPrefixReplace.1 '/boston/runScratch'
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.netPathPrefixSearch.1 '\\boston.nscamg.local\runScratch'
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.netPathPrefixSearchReplaceSuffixes '1'
#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.sequenceProcessBaseName 'NextSeq 500/550 Run'

# For dev-lims, set the test location(s).
## sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar set -y -f $HOST  nextseq.v2.seqservice.eventFileDirectory.1 '/boston/runScratch/test/gls_events_neseq'

## Check

#sudo -i -u glsjboss java -jar /opt/gls/clarity/tools/propertytool/omxprops-ConfigTool.jar export | grep nextseq.v2

### -- end section not necessary to do when re-installing ---


# 5. Enable & Start service
##sudo systemctl enable nextseq_seqservice-v2 ???
sudo service nextseq_seqservice-v2 start
