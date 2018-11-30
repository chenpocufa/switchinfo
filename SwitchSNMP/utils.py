import re


def parse_port_list(string, limit=None):
    ports = dict()
    for pos, byte in enumerate(string):
        binary = format(ord(byte),'08b')
        offset = 8 * pos
        for binpos, binbyte in enumerate(binary):
            index = binpos+offset+1
            # print('Port: %d Byte: %s' % (index, binbyte))
            if binbyte=='1':
                ports[index] = True
            else:
                ports[index] = False
            if limit and index >= limit:
                return ports
    return ports


def parse_mac(mac):
    mac_address = []
    for char in mac:
        mac_address.append(ord(char))
    return mac_address


def last_section(oid):
    match = re.match(r'.+\.([0-9]+)', oid)
    if match:
        return match.group(1)


def mac_parse_oid(oid):
    octets = oid.split('.')
    string = ''
    for octet in octets:
        octet = int(octet)
        if octet <= 0x0f:
            string += '0'
        string += format(octet, 'x')
    return string


def mac_string(mac_address):
    mac_string = ''
    for octet in mac_address:
        octet = ord(octet)
        if octet <= 0x0f:
            mac_string += '0'
        # Format as lower case hex digit without prefix
        mac_string += format(octet, 'x')
    return mac_string


def ip_string(ip):
    string = ''
    for section in ip:
        string += '%s.' % ord(section)
    return string[:-1]


def name_string(name):
    string = ''
    for char in name:
        string += '%s.' % ord(char)
    return string