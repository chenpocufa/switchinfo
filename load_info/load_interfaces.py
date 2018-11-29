from datetime import datetime

from django.db.utils import DataError

from easysnmp.exceptions import EasySNMPTimeoutError

from switchinfo.SwitchSNMP.select import get_switch
from switchinfo.models import Interface, Switch, Vlan


def load_interfaces(switch, now=None):
    if not now:
        now = datetime.now()
    device = get_switch(switch)
    interfaces = device.interfaces_rfc()
    try:
        interface_vlan = device.vlan_ports()
    except ValueError as exception:
        print(exception)
        print('Using pvid')
        interface_vlan = device.vlan_ports_pvid()

    uptime = device.uptime()
    if not interfaces:
        raise ValueError('No interfaces found on switch')

    ports_rev = dict()
    if switch.type == 'Cisco':
        vlans = Vlan.objects.filter(on_switch=switch, vlan__gt=0)
        if not vlans:
            raise ValueError('No vlans on switch, run load_vlans')

        ports = device.bridgePort_to_ifIndex()

        for vlan in vlans:
            try:
                ports_temp = device.bridgePort_to_ifIndex(vlan=vlan.vlan)
                if not ports_temp:
                    print('No ports found in vlan %d' % vlan.vlan)
                    continue
                for bridge_port, if_index in ports_temp.items():
                    ports[bridge_port] = if_index
                    ports_rev[if_index] = bridge_port
            except EasySNMPTimeoutError:
                pass
    else:
        ports = device.bridgePort_to_ifIndex()

    if not ports:
        raise ValueError('bridgePort to ifIndex conversion table not found')

    cdp_multi = device.cdp_multi()

    poe_status = device.interface_poe_status()
    if poe_status and not switch.has_poe:
        switch.has_poe = True
        switch.save()

    # for bridge_port, if_index in ports.items():
    for if_index in interfaces['type'].keys():
        if if_index not in ports_rev:
            bridge_port = (str(int(if_index[-2:])))
        else:
            bridge_port = ports_rev[if_index]

        name = interfaces['name'][if_index]
        # 117 is gigabitEthernet on HP
        if not interfaces['type'][if_index] == '6' \
                and not interfaces['type'][if_index] == '117':
            # print('Interface type %s' % interfaces['type'][if_index])
            continue
        if name == 'Fa0':
            continue

        interface, new = Interface.objects.get_or_create(
            switch=switch,
            index=if_index,
            interface=interfaces['name'][if_index],
        )
        if not new:
            if not interface.status == int(interfaces['status'][if_index]):
                interface.link_status_changed = datetime.now()
        interface.description = interfaces['alias'][if_index]

        if if_index in interfaces['high_speed']:
            interface.speed = interfaces['high_speed'][if_index]
        else:
            interface.speed = None
        # print(if_index)
        # print(interfaces['status'][if_index])
        interface.status = int(interfaces['status'][if_index])
        interface.admin_status = interfaces['admin_status'][if_index]

        if poe_status and bridge_port in poe_status:
            interface.poe_status = poe_status[bridge_port]
        else:
            interface.poe_status = None
        # print('cdp')
        # pprint(cdp_multi)

        neighbor = get_neighbors(interface.index, cdp_multi, switch)

        if not neighbor and interface.neighbor:
                if interface.neighbor_set_by == switch:
                    print('Clearing neigbor %s from %s, set by %s'
                          % (interface.neighbor,
                             interface,
                             interface.neighbor_set_by))
                    interface.neighbor = None
                else:
                    print('Keeping neigbor %s on %s set by %s' %
                          (interface.neighbor,
                           interface,
                           interface.neighbor_set_by))

        elif isinstance(neighbor, Switch):
            interface.neighbor = neighbor
            interface.neighbor_set_by = switch
        else:
            interface.neighbor_string = neighbor

        if not switch.type == 'Cisco' and not switch.type == 'CiscoSB' and not switch.type == 'Aruba':
            key = int(bridge_port)
        else:
            key = int(if_index)

        if key not in interface_vlan:
            # print('%d not in interface_vlan' % key)
            continue
        if not interface_vlan[key]:
            interface.vlan = None
        else:
            vlan = interface_vlan[key]
            try:
                interface.vlan = Vlan.objects.get(vlan=vlan)
                interface.vlan.has_ports = True
                interface.vlan.save()
            except Vlan.DoesNotExist:
                print('Missing vlan %s, run load_vlans' % vlan)
        try:
            interface.save()
        except DataError as error:
            print(error)

        # if if_index in tagged_ports:
        #    for vlan in tagged_ports[if_index]:
        #        print('vlan %s is tagged on ifindex %s' % (vlan, if_index))
        #        # interface.tagged_vlans.add(vlan)

    del device.sessions[switch.ip]


def get_neighbors(index, cdp_multi, switch):
    if index in cdp_multi:
        for neighbor in cdp_multi[index].values():
            if 'ip' not in neighbor:
                neighbor['ip'] = None
            if 'device_id' not in neighbor:
                neighbor['device_id'] = None

            if neighbor['ip']:
                neighbor_switch = Switch.objects.filter(ip=neighbor['ip'])
            elif neighbor['device_id']:
                neighbor_switch = Switch.objects.filter(name=neighbor['device_id'].split('.')[0])
            else:
                return
            if neighbor_switch and len(neighbor_switch) > 0:
                neighbor_switch = neighbor_switch.first()
                print('%s is a valid neighbor' % neighbor_switch)

                remote_interface = neighbor['remote_port']
                # if neighbor_switch.type == 'Cisco':
                #    remote_interface = re.sub(r'([A-Z][a-z]).+?([0-9\/]+)', r'\1\2', remote_interface)
                # elif neighbor_switch.type == 'Extreme':
                #    remote_interface = re.sub(r'Slot:\s+([0-9]+), Port:\s([0-9]+)', r'\1:\2', remote_interface)
                remote_interface = neighbor_switch.shorten_interface_name(remote_interface)
                # Set neighbor on the remote interface in case the current switch does not broadcast
                # remote = Interface.objects.filter(switch=neighbor_switch, interface=remote_interface)
                try:
                    remote = Interface.objects.get(switch=neighbor_switch,
                                                   interface=remote_interface)
                    remote.neighbor = switch
                    remote.neighbor_set_by = switch
                    remote.save()
                except Interface.DoesNotExist:
                    print('No interface named %s on %s' % (remote_interface, neighbor_switch))
                return neighbor_switch  # Valid neighbor found
                # break  # Valid neighbor found, break loop
            else:
                print('Unknown neighbor: ' + (neighbor['ip'] or neighbor['device_id']))
        return '%s\n%s\n%s' % (
            neighbor['device_id'],
            neighbor['ip'],
            neighbor['platform'])
    return None