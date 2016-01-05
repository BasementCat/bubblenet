import os
import re


class Error(Exception):
    pass


class AddressError(Error):
    pass


class AddressParseError(AddressError):
    pass


class EndpointError(Error):
    pass


class EndpointParseError(EndpointError):
    pass


class Address(object):
    @classmethod
    def from_string(self, value):
        for cls in self.__subclasses__():
            try:
                return cls(value)
            except AddressParseError:
                continue
        raise AddressError("Could not determine type of address", value)

    def __str__(self):
        return 'undefined'

    def __repr__(self):
        return '{}("{}")'.format(self.__class__.__name__, str(self))


class IPAddress(Address):
    pass


class IPv4Address(IPAddress):
    def __init__(self, value):
        if re.match(ur'^[\d.]{7,15}$', value):
            value = value.split('.')
            if len(value) == 4:
                int_value = 0
                for i in range(4):
                    try:
                        if len(value[i]) > 1 and value[i].startswith('0'):
                            raise AddressParseError("Octets may not start with '0'", value[i])
                        octet = int(value[i])
                        if octet < 0 or octet > 255:
                            raise AddressParseError("Octet is out of range", octet)
                        int_value |= (octet << ((3 - i) * 8))
                    except ValueError:
                        raise AddressParseError("Octet is not an integer", value[i])
                self.value = int_value
                return
            raise AddressParseError("Not enough octets", '.'.join(value))
        raise AddressParseError("Not an IPv4 address", value)

    def __str__(self):
        out = []
        for i in range(4):
            out.append(str((self.value >> ((3 - i) * 8)) & 255))
        return '.'.join(reversed(out))


class IPv6Address(IPAddress):
    def __init__(self, value):
        if re.match(ur'^[\da-f:]{2,39}$', value, re.I):
            if re.search(ur':{3,}', value):
                raise AddressParseError("Invalid use of '::'", value)
            if value.startswith(':') or value.endswith(':'):
                if not value.startswith('::') and not value.endswith('::'):
                    raise AddressParseError("IPv6 addresses may not start or end with ':'", value)
            halves = map(lambda v: filter(None, v), map(lambda v: v.split(':'), value.split('::')))
            if len(halves) == 1:
                halves.append([])
            a, b = halves[:2]
            if (len(a) + len(b) + (1 if len(b) else 0)) > 8 or len(halves) > 2:
                raise AddressParseError("IPv6 address is too long", value)
            value = a + ['0' for _ in range(8 - (len(a) + len(b)))] + b
            int_value = 0
            for i in reversed(range(8)):
                try:
                    int_value |= int(value[i], 16) << (i * 16)
                except ValueError:
                    raise AddressParseError("Part is not a hex integer", value[i])
            self.value = int_value
            return
        raise AddressParseError("Not an IPv6 address", value)

    def __str__(self):
        out = []
        for i in reversed(range(8)):
            out.append('{:04x}'.format((self.value >> (i * 16)) & 65535))
        return ':'.join(reversed(out))


class UnixSocketAddress(Address):
    def __init__(self, value):
        value = os.path.normpath(os.path.abspath(value))
        # TODO: check if the path is a socket
        if os.path.exists(value):
            self.value = value
            return
        raise AddressParseError("Does not appear to be a unix socket", value)

    def __str__(self):
        return self.value


class Endpoint(object):
    def __init__(self, value=None, host=None, port=None):
        self.host = host
        self.port = port
        if value is not None:
            match = re.search(ur'^(.*?)?(?::(\d+))?$', value)
            if match:
                if match.group(0):
                    self.host = match.group(0)
                if match.group(1):
                    try:
                        self.port = int(match.group(1))
                    except ValueError:
                        raise EndpointParseError("Port is not an integer", match.group(1))
            raise EndpointParseError("Can't parse endpoint", value)
        if self.host is not None:
            self.host = Address.from_string(self.host)
