import sys
sys.path.insert(0, '/var/www/html/lims/reagents-ui/backend')

from api import app as application
application.kits_file = '/var/db/kits/kits.yml'
application.load_kits()

