import threading
import socket
import ssl
import select

from bubbler import Bubbler


class PublisherMixin(object):
    def __init__(self, context=None, context_name=None):
        self.publisher_contexts = []
        self.add_publisher_context(context=context, context_name=context_name)

    def add_publisher_context(self, context=None, context_name=None):
        if context:
            self.publisher_contexts.append(context)
        elif context_name:
            self.publisher_contexts.append(Bubbler.getContext(context_name))

    def publish(self, *args, **kwargs):
        return [context.trigger(*args, **kwargs) for context in self.publisher_contexts]


class Listener(PublisherMixin):
    def __init__(self, host, port=None, start_now=True, family=socket.AF_INET, type_=socket.SOCK_STREAM, backlog=1, *args, **kwargs):
        super(Listener, self).__init__(*args, **kwargs)

        assert family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX),
            "Unsupported family (need one of AF_INET, AF_INET6, or AF_UNIX)"

        self.host = str(host)
        if family in (socket.AF_INET, socket.AF_INET6):
            self.port = int(port)
        else:
            self.port = None
        self.family = family
        self.type_ = type_
        self.backlog = backlog

        self.ssl = None
        self.lock = threading.RLock()
        self.listen_socket = None
        self.started = False
        self.children = {}

        if start_now:
            self.start()

    def make_ssl(self, *args, **kwargs):
        with self.lock:
            self.ssl = (args, kwargs)

            self._init_ssl()

    def _init_ssl(self):
        with self.lock:
            if self.ssl and self.started and self.listen_socket:
                self.listen_socket = ssl.wrap_socket(self.listen_socket, *self.ssl[0], **self.ssl[1])

    def start(self, restart=True):
        with self.lock:
            if self.started:
                if restart:
                    self.stop()
                else:
                    return

            self.listen_socket = socket.socket(self.family, self.type_)
            if self.family == socket.AF_UNIX:
                self.listen_socket.bind(self.host)
            else:
                self.listen_socket.bind((self.host, self.port))
            self.listen_socket.listen(self.backlog)
            self.started = True

            self._init_ssl()

        self.publish('listener/start', listener=self)

    def stop(self):
        with self.lock:
            if self.started:
                self.listen_socket.shutdown()
                self.listen_socket.close()
                self.listen_socket = None
                self.started = False

        self.publish('listener/stop', listener=self)

    def accept(self):
        with self.lock:
            if self.started:
                new_sock, addr = self.accept()
                if self.family == socket.AF_UNIX:
                    host, port = addr, None
                else:
                    host, port = list(addr)[:2]
                return Connection(host, port=port, inbound=True, existing_socket=new_sock, listener=self, family=self.family, type_=self.type_)

    def all_sockets(self):
        with self.lock:
            out = [self.listen_socket] + [c.connect_socket for c in self.children.values() if c.connect_socket and c.connected]

    def __eq__(self, other):
        with self.lock:
            if other is self:
                return True
            if other is self.listen_socket:
                return True
            return False

    def _add_child(self, conn):
        with self.lock:
            if conn.connect_socket in self.children:
                raise KeyError(str(conn.connect_socket))
            self.children[conn.connect_socket] = conn

    def _remove_child(self, conn):
        with self.lock:
            del self.children[conn.connect_socket]

    def _get_child(self, conn_sock):
        with self.lock:
            return self.children[conn_sock]


class Connection(PublisherMixin):
    def __init__(self, host, port=None, connect_now=True, inbound=False, existing_socket=None, listener=None, family=socket.AF_INET, type_=socket.SOCK_STREAM, recv_bufsize=None, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)

        assert family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX),
            "Unsupported family (need one of AF_INET, AF_INET6, or AF_UNIX)"

        self.host = str(host)
        if family in (socket.AF_INET, socket.AF_INET6):
            self.port = int(port)
        else:
            self.port = None
        self.family = family
        self.type_ = type_
        self.recv_bufsize = recv_bufsize or 8192

        self.ssl = None
        self.lock = threading.RLock()
        self.connect_socket = None
        self.connected = False
        self.inbound = None
        self.listener = None

        if inbound:
            assert existing_socket, "An inbound connection requires an existing socket"
            self.connect_socket = existing_socket
            self.connected = True
            self.inbound = True
            self.listener = listener
            if self.listener:
                self.listener._add_child(self)

            self.publish('connection/inbound', connection=self)
        else:
            if connect_now:
                self.connect()

    def make_ssl(self, *args, **kwargs):
        with self.lock:
            self.ssl = (args, kwargs)

            self._init_ssl()

    def _init_ssl(self):
        with self.lock:
            if self.ssl and self.connected and self.connect_socket:
                self.connect_socket = ssl.wrap_socket(self.connect_socket, *self.ssl[0], **self.ssl[1])

    def connect(self, reconnect=True):
        with self.lock:
            assert not self.inbound, "Can't connect an inbound socket"
            if self.connected:
                if reconnect:
                    self.disconnect()
                else:
                    return

            self.connect_socket = socket.socket(self.family, self.type_)
            if self.family == socket.AF_UNIX:
                self.connect_socket.connect(self.host)
            else:
                self.connect_socket.connect((self.host, self.port))
            self.connected = True

            self._init_ssl()

        self.publish('connection/outbound', connection=self)

    def disconnect(self):
        with self.lock:
            if self.connected:
                self.connect_socket.shutdown()
                self.connect_socket.close()
                self.connect_socket = None
                self.connected = False
                if self.listener:
                    self.listener._remove_child(self)

        self.publish('connection/disconnect', connection=self)

    def send(self, data, send_all=True):
        with self.lock:
            assert self.connected, "Can't send to a disconnected socket"
            if send_all:
                return self.connect_socket.sendall(data)
            return self.connect_socket.send(data)

    def recv(self, bufsize=None):
        with self.lock:
            assert self.connected, "Can't receive from a disconnected socket"
            return self.connect_socket.recv(bufsize or self.recv_bufsize)


def Poller(object):
    ALL_METHODS = ['epoll', 'poll', 'select', 'kqueue', 'kevent']
    SUPPORTED_METHODS = ['select']

    def __init__(self, method=None, method_priority=None):
        if method:
            assert method in self.ALL_METHODS, "Poll/select method {} does not exist".format(method)

            if method not in self.SUPPORTED_METHODS:
                raise NotImplementedError("Poll/select method {} is not implemented".format(method))

            assert getattr(select, method, None), "Poll/select method {} is not available on this platform".format(method)

            self.method = method
        else:
            valid_methods = [method for method in self.SUPPORTED_METHODS if getattr(select, method, None)]
            if not valid_methods:
                raise NotImplementedError("No implemented poll or select methods are available on this platform")
            self.method = valid_methods[0]


# class ConnectionGroup(object):
#     def __init__(self, listeners=None, connections=None):
#         self.listeners = (listeners or [])[:]
#         self.connections = (connections or [])[:]

#     def refresh(self, timeout)