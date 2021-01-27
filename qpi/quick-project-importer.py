WSGIDaemonProcess importer2 user=glsai group=claritylims python-home=/opt/nsc/envs/nsc-python27
Alias /qpi/static/ /opt/gls/clarity/customextensions/lims/qpi/static/
WSGIScriptAlias /qpi /opt/gls/clarity/customextensions/lims/qpi/qpi.wsgi

<Directory /opt/gls/clarity/customextensions/lims/qpi>
	WSGIProcessGroup importer2
	WSGIApplicationGroup %{GLOBAL}
	Require all granted
</Directory>

