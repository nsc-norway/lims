
sudo lvs
sudo lvresize -L22G internvg/opt
sudo xfs_growfs /opt

sudo lvresize -L20G internvg/var
sudo xfs_growfs /var

