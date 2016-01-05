import unittest

from bubblenet import (
    Address,
    IPAddress,
    IPv4Address,
    IPv6Address,
    AddressParseError,
    )


class ParsingTest(unittest.TestCase):
    # Test cases taken from https://en.wikipedia.org/wiki/Module:IPAddress/testcases
    valid_v4 = [
        '200.200.200.200',
        '0.0.0.0',
        '255.255.255.255',
    ]
    invalid_v4 = [
        ' 200.200.200.200',  # whitespace not currently allowed
        '200.200.200.200 ',  # whitespace not currently allowed
        '200.200.256.200',
        '200.200.200.200.',
        '200.200.200',
        '200.200.200.2d0',
        '00.00.00.00',  # according to talkpage, leading zeroes unacceptable.
        '100.100.020.100',  # according to talkpage, leading zeroes unacceptable.
        '-1.0.0.0',
        '200000000000000000000000000000000000000000000000000000000000000000000000000000.200.200.200',
        '00000000000005.10.10.10',
    ]
    valid_v6 = [
        ('00AB:0002:3008:8CFD:00AB:0002:3008:8CFD',  # full length
            '00ab:0002:3008:8cfd:00ab:0002:3008:8cfd'),
        ('00ab:0002:3008:8cfd:00ab:0002:3008:8cfd',  # lowercase
            '00ab:0002:3008:8cfd:00ab:0002:3008:8cfd'),
        ('00aB:0002:3008:8cFd:00Ab:0002:3008:8cfD',  # mixed case
            '00ab:0002:3008:8cfd:00ab:0002:3008:8cfd'),
        ('AB:02:3008:8CFD:AB:02:3008:8CFD',  # abbreviated
            '00ab:0002:3008:8cfd:00ab:0002:3008:8cfd'),
        ('AB:02:3008:8CFD::02:3008:8CFD',  # correct use of ::
            '00ab:0002:3008:8cfd:0000:0002:3008:8cfd'),
        ('::',  # unassigned IPv6 address
            '0000:0000:0000:0000:0000:0000:0000:0000'),
        ('::1',  # loopback IPv6 address
            '0000:0000:0000:0000:0000:0000:0000:0001'),
        ('0::',  # another name for unassigned IPv6 address
            '0000:0000:0000:0000:0000:0000:0000:0000'),
        ('0::0',  # another name for unassigned IPv6 address
            '0000:0000:0000:0000:0000:0000:0000:0000'),
    ]
    invalid_v6 = [
        '00AB:00002:3008:8CFD:00AB:0002:3008:8CFD',  # at most 4 digits per segment
        ':0002:3008:8CFD:00AB:0002:3008:8CFD',  # can't remove all 0s from first segment unless using ::
        '00AB:0002:3008:8CFD:00AB:0002:3008:',  # can't remove all 0s from last segment unless using ::
        'AB:02:3008:8CFD:AB:02:3008:8CFD:02',  # too long
        'AB:02:3008:8CFD::02:3008:8CFD:02',  # too long
        'AB:02:3008:8CFD::02::8CFD',  # can't have two ::s
        'GB:02:3008:8CFD:AB:02:3008:8CFD',  # Invalid character G
        '2:::3',  # illegal: three colons
    ]

    def test_valid_address_v4(self):
        for addr in self.valid_v4:
            self.assertEquals(addr, str(IPv4Address(addr)), msg=repr(addr))

    def test_invalid_address_v4(self):
        for addr in self.invalid_v4:
            try:
                IPv4Address(addr)
            except AddressParseError:
                continue
            self.assertTrue(False, msg=repr(addr))

    def test_valid_address_v6(self):
        for addr, correct in self.valid_v6:
            try:
                parsed = str(IPv6Address(addr))
                self.assertEquals(correct, parsed, msg=repr(correct) + ' != ' + repr(parsed))
            except AddressParseError as e:
                self.assertTrue(False, str(e))

    def test_invalid_address_v6(self):
        for addr in self.invalid_v6:
            try:
                IPv6Address(addr)
            except AddressParseError:
                continue
            self.assertTrue(False, msg=repr(addr))