import sys
sys.path.insert(0, '/opt/gls/clarity/customextensions/lims/reagents-ui/backend')

import api
application = api.app
api.kits_file = '/var/db/kits/kits.yml'
api.load_kits()

