import socket
import select
import logging
import re

import bubbler

servers = {}
clients = {}
all_socks = []

log = logging.getLogger(__name__)

class NetworkError(Exception):
    pass

friendly_protocol_names = {} # for example, could map 'https' to ('tcp', True) and 'irc' to ('tcp', False)
protocol_map = {
    'tcp': socket.SOCK_STREAM,
    'udp': socket.SOCK_DGRAM,
}

def parse_service(service_, default_port = None, default_protocol = 'tcp', default_ssl = False, bubbler_context = None):
    service = service_

    protocol = default_protocol
    ssl = default_ssl
    address = None
    port = default_port
    is_v6 = False

    # Test for a protocol
    protocol_match = re.match(ur'^(tcp|udp)(?:\+(ssl))?://(.*)$', service)
    if protocol_match:
        protocol = protocol_match.group(1)
        ssl = protocol_match.group(2) == 'ssl'
        service = protocol_match.group(3)

    # Test for an IPv4 address match
    v4_match = re.match(ur'^([0-9.]{7,15})(?::(\d{1,5}))?$', service)
    if v4_match:
        address = v4_match.group(1)
        port = int(v4_match.group(2) or 0) or default_port
        parts = map(int, address.split('.'))
        if len(parts) != 4 or max(*parts) > 255 or min(*parts) < 0:
            raise NetworkError("Invalid IPv4 address: '%s'" % (address,))

    if address is None:
        # Test for a v6 address, with port
        v6_port_match = re.match(ur'^\[([^\]]{2,39})\]:(\d{1,5})$', service)
        if v6_port_match:
            service = v6_port_match.group(1)
            port = int(v6_port_match.group(2))

    if address is None and len(re.sub(ur'[^:]', '', service)) > 1:
        # Test for a raw v6 address (port has already been extracted)
        v6_match = re.match(ur'^[0-9a-fA-F:]{2,39}$', service)
        if v6_match:
            if '::' in service:
                a, b = map(lambda s: filter(None, s.split(':')), service.split('::'))
                parts = a + ['0' for _ in range(0, 8 - (len(a) + len(b)))] + b
            else:
                parts = service.split(':')
            parts = map(lambda s: int('0x' + s, 0), parts)
            if max(*parts) > 65535 or min(*parts) < 0:
                raise NetworkError("Invalid IPv6 address: '%s'" % (service,))
            address = ':'.join(['%04x' % i for i in parts])

            is_v6 = True

    if address is None:
        # Assume that what's left is a hostname
        if len(re.sub(ur'[^.]', '', service)) > 1 or len(re.sub(ur'[^:]', '', service)) > 1 or re.match(ur'^[0-9.]+$', service):
            raise NetworkError("Invalid hostname: '%s'" % (service_,))
        hostname_match = re.match(ur'^([^:]+)(?::(\d{1,5}))$', service)
        if hostname_match:
            address = hostname_match.group(1)
            port = int(hostname_match.group(2) or 0) or default_port

    # Sanity check
    if address is None:
        raise NetworkError("Could not find a valid hostname or IP address in '%s'" % (service_,))

    port = port or default_port
    if port is None:
        raise NetworkError("Could not find a valid port in '%s'" % (service_,))

    if protocol in friendly_protocol_names:
        protocol, ssl = friendly_protocol_names[protocol]

    if protocol not in protocol_map:
        raise NetworkError("Invalid protocol '%s' for service '%s'" % (protocol, service_))

    return (protocol_map[protocol], ssl, address, port, is_v6)

class Server(object):
    def __init__(self, host, port, v6 = False):
        global servers, all_socks

        self.bubbler_context = bubbler_context if isinstance(bubbler_context, bubbler.Bubbler) else bubbler.Bubbler.getContext(bubbler_context)

        self.host = host if host else ("::" if v6 else "0.0.0.0")
        self.port = port
        self.v6 = v6

        self.sock = socket.socket(socket.AF_INET6 if self.v6 else socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(16)

        log.info("Listening on %s", self)

        servers[self.sock] = self
        all_socks.append(self.sock)

        self.bubbler_context.trigger('Network/Server/Start', self)

    @classmethod
    def from_service(self, service, bubbler_context = None):
        protocol, ssl, host, port, v6 = parse_service(service)

        if protocol != socket.SOCK_STREAM:
            raise NotImplementedError("Protocols other than SOCK_STREAM are not supported right now")

        if ssl:
            raise NotImplementedError("SSL support is not implemented yet")

        return self(host, port, v6)

    def stop(self):
        global servers, all_socks

        del(servers[self.sock])
        all_socks.remove(self.sock)
        self.sock.close()
        log.info("Stopped listening on %s", self)
        self.bubbler_context.trigger('Network/Server/Stop', self)

    def on_new_sock(self):
        global clients, all_socks
        new_sock = self.sock.accept()[0]
        out = Client(new_sock, self)
        clients[new_sock] = out
        all_socks.append(new_sock)
        self.bubbler_context.trigger('Network/Server/NewClient', self, out)

    def __str__(self):
        if self.v6:
            return "Server([%s]:%d)" % (self.host, self.port)
        else:
            return "Server(%s:%d)" % (self.host, self.port)

class Client(object):
    def __init__(self, new_sock, listener):
        self.sock = new_sock
        self.local_host, self.local_port = self.sock.getsockname()
        self.remote_host, self.remote_port = self.sock.getpeername()
        self.data_queue = ""
        self.server = listener
        log.info("New client: %s->%s", self, self.server)

    def on_new_data(self):
        d = self.sock.recv(1024)
        self.data_queue += d
        log.debug("Got %d bytes from %s:%d", len(d), self.remote_host, self.remote_port)
        self.server.bubbler_context.trigger('Network/Client/NewData', self)

    def close(self):
        global clients, all_socks
        self.server.bubbler_context.trigger('Network/Client/Disconnect/Close', self)
        del(clients[self.sock])
        all_socks.remove(self.sock)
        self.sock.close()

    def __str__(self):
        return "%s:%d"%(self.remote_host, self.remote_port)

def refresh(selectTimeout = 0.1):
    global all_socks, servers, clients
    readSocks = all_socks
    read, write, exc = select.select(readSocks, [], [], selectTimeout)
    for sock in read:
        if sock in servers:
            servers[sock].on_new_sock()
        else:
            clients[sock].on_new_data()

def shutdown():
    global all_socks
    for sock in all_socks:
        sock.close()