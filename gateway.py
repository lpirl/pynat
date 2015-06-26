# coding: utf-8

"""
This module includes a DNAT port forwarding implementation.

It mainly consists of two socket dispatchers (see Python's asyncore
module for detailed information on those).
The first dispatcher is responsible for the port forwarding.
To be able to close a forwarding port from within another process,
a second dispatcher listens on a socket and closes the first one upon
receiving a pre-shared secret.
Socked addresses can be easily serialized and thereby shared between
processes, stored in a file or database etc.

    --------               |
    |client|––.            |
    --------   \     ------------------       ---------------
                –––––| we (forwarder) |–––––––| remote host |
    --------   /     ------------------       ---------------
    |client|––'            |
    --------               | <- possible NAT border

Inspired by:
http://code.activestate.com/recipes/483732-asynchronous-port-forwarding/
"""

from socket import error as SocketError
from os import remove

from threading import Thread
from socket import AF_INET, SOCK_STREAM, AF_UNIX
from asyncore import dispatcher, loop

from logging import info, debug


class PortForwarding(dispatcher):
    """
    This class handles the forwarding of traffic from a local port to
    a remote port.
    Therefore, it listens on the local port and connects to the remote
    host upon new connections.
    For each established connection, there will be a separate socket
    handler doing the actual forwarding.
    """

    IO_LOOP_THREAD = None

    @classmethod
    def ensure_io_loop_runs(cls):
        """
        Responsible for starting the GatewayDispatcher's main IO loop.
        """
        thread = cls.IO_LOOP_THREAD
        if thread is not None and thread.is_alive():
            return

        info(
            ('restarting' if thread else 'starting') +
            " the GatewayDispatcher's main IO loop"
        )

        thread = Thread(
            target=loop,
            name=cls.__name__
        )
        thread.start()
        cls.IO_LOOP_THREAD = thread

    def __init__(self, local_ip, remote_host, remote_port,
                 backlog=5, bufsize=4096, preferred_local_port=0):
        """
        Sets up the listening on a local port for connections to forward.
        """
        dispatcher.__init__(self)

        self.remote_address = (remote_host, remote_port)
        self.bufsize = bufsize

        # initialize the listening:
        self.create_socket(AF_INET, SOCK_STREAM)
        self.set_reuse_addr()
        try:
            self.bind((local_ip, preferred_local_port))
        except SocketError:
            self.bind((local_ip, 0))
        self.listen(backlog)

        self.__class__.ensure_io_loop_runs()

    def handle_accept(self):
        """ establishes a new forwarding for a new client """
        socket_and_address = self.accept()
        if socket_and_address is None:
            debug("accepted socket connection but now it's gone…")
            return
        connection, address = socket_and_address
        debug('accepted connection from %s' % address[0])

        buffers = self.ForwardingBuffers()

        to_client = self.ConnectionToClient(
            connection,
            buffers,
            self.bufsize
        )
        to_remote_host = self.ConnectionToRemoteHost(
            self.remote_address,
            buffers,
            self.bufsize
        )

        to_client.buddy_dispatcher = to_remote_host
        to_remote_host.buddy_dispatcher = to_client

    def get_listen_port(self):
        """ returns the local port we are listening on """
        return self.socket.getsockname()[1]

    def handle_close(self):
        """
        Closes the listening socket.
        This does not close existing connections. Those will be closed
        by either of the endpoints.
        """
        debug(
            'closing PortForwarding at %s:%s' % self.getsockname()
        )
        self.close()

    class ForwardingBuffers(object):
        """
        Shared data buffers for forwarding dispatchers.
        """

        def __init__(self):
            self.to_client = str()
            self.to_remote_host = str()

    class ConnectionToClient(dispatcher):
        """
        This class handles the socket that points to a client.

        It basically receives sent data, buffers it, and makes it
        readable for the `ConnectionToRemoteHost` (and vice versa).

        TODO: can probably be generalized w/ ConnectionToRemoteHost
        """

        def __init__(self, connection, buffers, bufsize):
            """
            Initializes the dispatch of the already existing connection.
            """
            dispatcher.__init__(self, connection)
            self.buffers = buffers
            self.bufsize = bufsize
            self.buddy_dispatcher = None

        def handle_connect(self):
            pass

        def handle_read(self):
            """ client --> buffer """
            read = self.recv(self.bufsize)
            self.buffers.to_remote_host += read

        def writable(self):
            return (len(self.buffers.to_client) > 0)

        def handle_write(self):
            """ client <-- buffer """
            sent_count = self.send(self.buffers.to_client)
            self.buffers.to_client = self.buffers.to_client[sent_count:]

        def handle_close(self):
            debug(
                'connection to client %s closed' % self.getsockname()[0]
            )
            self.close()

            # if this socket to the client is closed, the one to the
            # remote host must be closed as well
            buddy = self.buddy_dispatcher
            if buddy:
                debug(
                    "closing buddy socket to %s as well" % (
                        buddy.getsockname()[0],
                ))
                buddy.close()

    class ConnectionToRemoteHost(dispatcher):
        """
        This class handles the socket that points to the remote host.

        It basically reads data from the `ConnectionToClient` and
        sends it to the remote host (and vice versa).

        TODO: can probably be generalized w/ ConnectionToClient
        """

        def __init__(self, remote_address, buffers, bufsize):
            """
            Initializes the dispatch of a new connection to the remote
            host.
            """
            dispatcher.__init__(self)
            self.buffers = buffers
            self.bufsize = bufsize
            self.buddy_dispatcher = None
            self.create_socket(AF_INET, SOCK_STREAM)
            self.connect(remote_address)

        def handle_connect(self):
            pass

        def handle_read(self):
            """ buffer <-- remote host """
            read = self.recv(self.bufsize)
            self.buffers.to_client += read

        def writable(self):
            return (len(self.buffers.to_remote_host) > 0)

        def handle_write(self):
            """ buffer --> remote host """
            sent = self.send(self.buffers.to_remote_host)
            self.buffers.to_remote_host = self.buffers.to_remote_host[sent:]

        def handle_close(self):
            debug(
                'connection to remote host %s closed' % self.getsockname()[0]
            )
            self.close()

            # if this socket to the remote is closed, the one to the
            # client must be closed as well
            buddy = self.buddy_dispatcher
            if buddy:
                debug(
                    "closing buddy socket to %s as well" % (
                        buddy.getsockname()[0],
                ))
                buddy.close()


class PortForwardingTerminator(dispatcher):
    """
    This is a "server" that listens on a UNIX socket and closes a certain
    other socket/dispatcher and itself when receiving a pre-shared secret.

    It does **not** close established connections, it just disables new
    connections.

    TODO: also provide functionality to close established connections.
    """

    def __init__(self, socket_path, socket_secret, socket_to_close,
                 backlog=5, bufsize=4096):
        """
        Initializes the dispatch of a new connection to the remote host.
        """
        debug("PortForwardingTerminator initialized")
        dispatcher.__init__(self)

        self.socket_secret = socket_secret
        self.socket_to_close = socket_to_close
        self.bufsize = bufsize

        # intitialize the listening:
        self.create_socket(AF_UNIX, SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(socket_path)
        self.listen(backlog)

    def handle_accept(self):
        """ starts a dispatcher for a newly connecting client """
        socket_and_address = self.accept()
        if socket_and_address is None:
            debug("accpted socket connection but now it's gone…")
            return
        connection, address = socket_and_address
        debug('PortForwardingTerminator accepted connection')

        self.ConnectionToTerminator(
            connection,
            self.socket_secret,
            self.socket_to_close,
            self,
            self.bufsize
        )

    def handle_close(self):
        sockname = self.socket.getsockname()
        debug(
            "closing PortForwardingTerminator on '%s'" % sockname
        )
        remove(sockname)
        self.close()

    class ConnectionToTerminator(dispatcher):
        """
        This is the handler for any connected client connected to the
        "close server".
        If it receives the correct secret, it closes the
        ``PortForwarding`` (``forwarding_listener``)
        ``PortForwardingTerminator`` (``close_listener``)
        and itself.
        """

        def __init__(self, connection, secret, close_listener,
                     forwarding_listener, bufsize):
            """
            Initializes the dispatch of a new connection to the remote host.
            """
            debug("ConnectionToTerminator initialized")
            dispatcher.__init__(self, connection)
            self.secret = secret
            self.close_listener = close_listener
            self.forwarding_listener = forwarding_listener
            self.bufsize = bufsize
            self.recv_buf = ""

        def handle_read(self):
            recv = self.recv(self.bufsize)
            self.recv_buf += recv
            if len(self.recv_buf) > len(self.secret):
                debug("ConnectionToTerminator received invalid secret")
                self.handle_close()
                return
            if self.secret == self.recv_buf:
                debug("ConnectionToTerminator received correct secret")
                self.forwarding_listener.handle_close()
                self.close_listener.handle_close()
                self.handle_close()

        def writable(self):
            return False

        def handle_close(self):
            debug("ConnectionToTerminator closed")
            self.close()
