import re
from pprint import pprint

from switchinfo.SwitchSNMP.SwitchSNMP import SwitchSNMP
from switchinfo.models import Switch


def switch_info(ip=None, community=None, device=None, silent=True):
    if not device:
        device = SwitchSNMP(community=community, device=ip)
    else:
        ip = device.device
        community = device.community
    info = device.switch_info()
    if not info:
        return

    switch, new = Switch.objects.get_or_create(ip=ip)
    switch.community = community
    switch.type = switch_type(info['descr'])
    switch.name = info['name'].split('.')[0]
    switch.description = info['descr']

    if 'model' in info and not info['model'] == '':
        switch.model = info['model']
    else:
        switch.model = model_from_description(device, switch.type)

    switch.series = switch_series(switch)

    if not silent:
        pprint(info)
        print('Type: %s' % switch.type)
        print('Series: %s' % switch.series)
        print(switch.model)

    switch.save()
    return switch


def switch_type(descr):
    if descr.find('Cisco') == 0:
        return 'Cisco'
    elif descr.find('ExtremeXOS') == 0:
        return 'Extreme'
    elif descr.find('Aruba') == 0:
        return 'Aruba'
    elif descr.find('Hewlett-Packard') == 0:
        return 'HP'
    elif descr.find('Westermo') == 0:
        return 'Westermo'


def switch_series(switch):
    series = None
    if switch.type == 'Cisco':
        series = re.match(r'((?:WS|IE)-[A-Z0-9]+).*?$', switch.model)
    elif switch.type == 'Aruba':
        series = re.match(r'Aruba [A-Z0-9]+ ([A-Z0-9]+)', switch.description)

    if series:
        return series.group(1)


def model_from_description(description=None, device=None):
    if not description:
        description = device.create_list(oid='.1.3.6.1.2.1.47.1.1.1.1.2')  # ENTITY-MIB::entPhysicalDescr
    sw_type = switch_type(description)

    for string in description:
        if sw_type == 'Aruba':
            matches = re.match(r'Aruba [A-Z0-9]+\s(.+)\sSwitch', string)
        elif sw_type == 'Cisco':
            matches = re.match(r'Cisco.+?((:WS\-)?[cC][A-Z0-9\-]+).*switch', string, flags=re.DOTALL)
        elif sw_type == 'HP':
            matches = re.match(r'HP ([0-9\-]+) Switch Software', string)
        else:
            return None  # Unsupported type

        if matches:
            return matches.group(1)
