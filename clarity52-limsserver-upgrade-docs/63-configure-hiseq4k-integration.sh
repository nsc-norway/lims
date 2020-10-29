sudo yum --enablerepo=GLS_HiSeq3k4k install ClarityLIMS-Illumina-HiSeq3k4k-Package-v1

# Skip workflow installation prompt
# configure_extensions_illumina_hiseq3k4k_workflow-v1.sh

# Skip or run configure extensions script:
sudo -u glsjboss bash /opt/gls/clarity/config/configure_extensions_hiseq3k4k_sequencingservice-v1.sh
sudo chkconfig hiseq3k4k_seqservice-v1 on
sudo /etc/init.d/hiseq3k4k_seqservice-v1 start
sudo /etc/init.d/hiseq3k4k_seqservice-v1 log
#Ctrl-C