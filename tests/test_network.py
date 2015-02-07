import unittest

from bubblenet import network

class TestNetworkFuncs(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestNetworkFuncs, self).__init__(*args, **kwargs)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parse_service(self):
        self.assertEqual(network.parse_service('127.0.0.1:12'), ('tcp', False, '127.0.0.1', 12))
        self.assertEqual(network.parse_service('8.8.8.8:345'), ('tcp', False, '8.8.8.8', 345))
        self.assertEqual(network.parse_service('10.10.0.1:6789'), ('tcp', False, '10.10.0.1', 6789))
        self.assertEqual(network.parse_service('172.16.0.1:12345'), ('tcp', False, '172.16.0.1', 12345))

        self.assertEqual(network.parse_service('[::1]:12'), ('tcp', False, '0000:0000:0000:0000:0000:0000:0000:0001', 12))
        self.assertEqual(network.parse_service('[a::5]:345'), ('tcp', False, '000a:0000:0000:0000:0000:0000:0000:0005', 345))
        self.assertEqual(network.parse_service('[7:f::8]:6789'), ('tcp', False, '0007:000f:0000:0000:0000:0000:0000:0008', 6789))
        self.assertEqual(network.parse_service('[5:c:d:3::f]:12345'), ('tcp', False, '0005:000c:000d:0003:0000:0000:0000:000f', 12345))
        self.assertEqual(network.parse_service('[0123:4567:89ab:cdef:0123:4567:89ab:cdef]:80'), ('tcp', False, '0123:4567:89ab:cdef:0123:4567:89ab:cdef', 80))

        with self.assertRaises(network.NetworkError):
            network.parse_service('0.0.0.0:0')
        with self.assertRaises(network.NetworkError):
            network.parse_service('laskdjflkasjd')
        with self.assertRaises(network.NetworkError):
            network.parse_service('1234.1.2.3:75')
        with self.assertRaises(network.NetworkError):
            network.parse_service('1.2.3.4')
        with self.assertRaises(network.NetworkError):
            network.parse_service('3.6.7.3:')
        with self.assertRaises(network.NetworkError):
            network.parse_service('8.7.6.56:123456')
        with self.assertRaises(network.NetworkError):
            network.parse_service('1.2.3:4')

        with self.assertRaises(network.NetworkError):
            network.parse_service('[::]:0')
        with self.assertRaises(network.NetworkError):
            network.parse_service('[d::z]:4')
        with self.assertRaises(network.NetworkError):
            network.parse_service('[a::f]:123456')
        with self.assertRaises(network.NetworkError):
            network.parse_service('[::]')
        with self.assertRaises(network.NetworkError):
            network.parse_service('[::]:')

if __name__ == '__main__':
    unittest.main()