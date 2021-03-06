# from datetime import datetime

from django.core.management.base import BaseCommand  # , CommandError
# from django.utils import timezone
from django.db.utils import DataError

import switchinfo.SwitchSNMP.utils as utils
from switchinfo.models import Arp, Switch
from switchinfo.SwitchSNMP.select import get_switch


class Command(BaseCommand):
    help = 'Import ARP from switches'

    def add_arguments(self, parser):
        parser.add_argument('switch', nargs='+', type=str)

    def handle(self, *args, **options):
        switch = Switch.objects.get(name=options['switch'][0])
        device = get_switch(switch)

        arp = device.arp()
        # pprint(arp)
        # return

        for mac, ip in arp.items():
            if not len(mac) == 12:
                mac = utils.mac_string(mac)
            try:
                arp_db = Arp(mac=mac, ip=ip)
                arp_db.save()
            except DataError as error:
                print(error)
                print(mac)
                print(utils.mac_string(mac))
