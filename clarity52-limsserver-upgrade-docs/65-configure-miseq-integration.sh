sudo yum --enablerepo=GLS_Clarity_MiSeq install ClarityLIMS-Illumina-MiSeq-Package-v5

# Don't run this. It will only import the workflow:
#sudo -u glsjboss /opt/gls/clarity/config/configure_extensions_illumina_miseq_workflow-v5.sh

# No need to run this. It will import the configuration parameters, they are already there:
#sudo -u glsjboss /opt/gls/clarity/config/configure_extensions_miseq_sequencingservice-v5.sh

sudo chkconfig miseq_seqservice-v5 on
sudo /etc/init.d/miseq_seqservice-v5 start