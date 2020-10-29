sudo yum --enablerepo=GLS_Clarity_HiSeqXFile install ClarityLIMS-Illumina-HiSeq-X-File-Package-v1

# - Skip workflow import command configure_extensions_illumina_hiseqx_file_workflow-v1.sh

# - Run configuration command to make sure the properties are already installed
sudo -u glsjboss bash /opt/gls/clarity/config/configure_extensions_hiseqx_sequencingservice-v1.sh

# If any new properties added, also do configure them with the correct paths etc.
sudo chkconfig hiseqx_seqservice-v1 on
sudo /etc/init.d/hiseqx_seqservice-v1 start
sudo /etc/init.d/hiseqx_seqservice-v1 log