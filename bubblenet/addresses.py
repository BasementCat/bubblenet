import os
import re

from errors import (
    AddressError,
    AddressParseError,
    )


class Address(object):
    weight = 1024

    @classmethod
    def from_string(self, value):
        class_queue = self.__subclasses__()
        classes = []
        while class_queue:
            class_ = class_queue.pop()
            classes.append(class_)
            class_queue += class_.__subclasses__()

        for cls in sorted(classes, key=lambda v: v.weight):
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
    def __init__(self, value):
        raise AddressParseError("Cannot parse an IP address without knowing its type")


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
    weight = 2048

    def __init__(self, value):
        # Poor validation - perhaps this could be improved?
        if os.sep not in value and not value.endswith('.sock'):
            raise AddressParseError("Not a Unix socket", value)

        self.value = os.path.normpath(os.path.abspath(value))

    def __str__(self):
        return self.value
