# Export to EDDN

from collections import OrderedDict
import hashlib
import json
import numbers
from platform import system
import re
import requests
from sys import platform
import time

from config import applongname, appversion, config
from companion import category_map


timeout= 10	# requests timeout
module_re = re.compile('^Hpt_|^Int_|_Armour_')


class _EDDN:

    ### UPLOAD = 'http://localhost:8081/upload/'	# testing
    UPLOAD = 'http://eddn-gateway.elite-markets.net:8080/upload/'

    def __init__(self):
        self.session = requests.Session()

    def send(self, cmdr, msg):
        msg['header'] = {
            'softwareName'    : '%s [%s]' % (applongname, platform=='darwin' and "Mac OS" or system()),
            'softwareVersion' : appversion,
            'uploaderID'      : config.getint('anonymous') and hashlib.md5(cmdr.encode('utf-8')).hexdigest() or cmdr.encode('utf-8'),
        }
        msg['message']['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(config.getint('querytime') or int(time.time())))

        r = self.session.post(self.UPLOAD, data=json.dumps(msg), timeout=timeout)
        if __debug__ and r.status_code != requests.codes.ok:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s'  % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
        r.raise_for_status()

    def export_commodities(self, data):
        commodities = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if category_map.get(commodity['categoryname'], True):	# Check marketable
                commodities.append(OrderedDict([
                    ('name',          commodity['name']),
                    ('meanPrice',     int(commodity['meanPrice'])),
                    ('buyPrice',      int(commodity['buyPrice'])),
                    ('stock',         int(commodity['stock'])),
                    ('stockBracket',  commodity['stockBracket']),
                    ('sellPrice',     int(commodity['sellPrice'])),
                    ('demand',        int(commodity['demand'])),
                    ('demandBracket', commodity['demandBracket']),
                ]))
                if commodity['statusFlags']:
                    commodities[-1]['statusFlags'] = commodity['statusFlags']

        # Don't send empty commodities list - schema won't allow it
        if commodities:
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/commodity/3',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'commodities' : commodities,
                }
            })

    def export_outfitting(self, data):
        # Don't send empty modules list - schema won't allow it
        if data['lastStarport'].get('modules'):
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/outfitting/2',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'modules'     : sorted([module['name'] for module in data['lastStarport']['modules'].itervalues() if module_re.search(module['name']) and module.get('sku') in [None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'] and module['name'] != 'Int_PlanetApproachSuite']),
                }
            })

    def export_shipyard(self, data):
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if data['lastStarport'].get('ships'):
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/shipyard/2',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'ships'       : sorted([ship['name'] for ship in data['lastStarport']['ships']['shipyard_list'].values() + data['lastStarport']['ships']['unavailable_list']]),
                }
            })

# singleton
eddn = _EDDN()
