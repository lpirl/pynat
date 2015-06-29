# coding: utf-8

"""
This module includes a DNAT port forwarding implementation.

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
from socket import socket, AF_INET, SOCK_STREAM
from asyncore import dispatcher, loop

from logging import info, debug

if __debug__:
    from logging import basicConfig, DEBUG
    basicConfig(level=DEBUG)

class PortForwarding(dispatcher):
    """
    This class enables the forwarding of traffic from a local port to
    a remote port.

    Therefore, it listens on the local port and connects to the remote
    host upon new connections.

    For each established connection, there will be two separate sockets
    (one pointing  to the client, one pointing to the remote host)
    doing the actual forwarding.
    """

    IO_LOOP_THREAD = None

    @classmethod
    def ensure_io_loop_runs(cls):
        """
        Responsible for starting the PortForwarding's main IO loop.
        """
        thread = cls.IO_LOOP_THREAD
        if thread is not None and thread.is_alive():
            return

        info(
            ('restarting' if thread else 'starting') +
            " the PortForwarding's main IO loop"
        )

        thread = Thread(
            target=loop,
            name="asyncore IO loop for %s" % cls.__name__
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
        """ establishes a new connection for a connecting client """

        socket_and_address = self.accept()
        if socket_and_address is None:
            debug("accepted socket connection but now it's gone…")
            return
        socket_to_client, address = socket_and_address
        debug('accepted connection from %s:%i' % address)

        # establish a connection to the remote host for the connecting
        # client:
        debug('connecting to remote host %s:%i' % self.remote_address)
        socket_to_remote_host = socket(AF_INET, SOCK_STREAM)
        socket_to_remote_host.connect(self.remote_address)

        # initialize buffers for the forwarding:
        buffer_client_to_remote_host = self.__class__.ForwardingBuffer()
        buffer_remote_host_to_client = self.__class__.ForwardingBuffer()

        # create forwarding connections for both sockets:
        connection_to_client = self.EstablishedConnection(
            socket_to_client,
            buffer_client_to_remote_host,
            buffer_remote_host_to_client,
            self.bufsize
        )
        connection_to_remote_host = self.EstablishedConnection(
            socket_to_remote_host,
            buffer_remote_host_to_client,
            buffer_client_to_remote_host,
            self.bufsize
        )

        # tell both connections about the other one:
        connection_to_client.buddy_connection = connection_to_remote_host
        connection_to_remote_host.buddy_connection = connection_to_client

    @property
    def listen_port(self):
        """ returns the local port we are listening on """
        return self.socket.getsockname()[1]

    def handle_close(self):
        """
        Closes the listening socket.
        This does not close existing connections. Those will be closed
        by either of the endpoints.
        """
        debug('closing PortForwarding at %s:%s' % self.getsockname())
        self.close()

    class ForwardingBuffer(object):
        """
        A class containing a simple string buffer.

        It is used as a shared reference to the buffer among objects
        (because strings cannot be modified in-place).
        """

        def __init__(self):
            self._buffer = ""

        def add(self, value):
            """ add to the buffer """
            self._buffer += value

        def get(self):
            """ get the whole buffer """
            return self._buffer

        def remove(self, count):
            self._buffer = self._buffer[count:]

        def has_content(self):
            return bool(self)

    class EstablishedConnection(dispatcher):
        """
        This class handles the actual forwarding of data for an
        established socket connection.
        (This could be either to the client or to the remote host.)

        To do so, it does the following:
        * receive data and write it to the ``buffer_received``
        * read data from the ``buffer_to_send`` and send it
        """

        def __init__(self, socket_to_use, buffer_received, buffer_to_send,
                    bufsize):
            """
            Initializes the dispatch of an optionally already existing
            connection.
            """
            debug("initializing dispatcher for %s:%i"
                    % socket_to_use.getsockname())
            dispatcher.__init__(self, socket_to_use)
            self.buffer_received = buffer_received
            self.buffer_to_send = buffer_to_send
            self.bufsize = bufsize
            self.buddy_connection = None

        def handle_connect(self):
            pass

        def handle_read(self):
            """ receive into buffer """
            read = self.recv(self.bufsize)
            self.buffer_received.add(read)

        def writable(self):
            return self.buffer_to_send.has_content()

        def handle_write(self):
            """ send from buffer """
            sent_count = self.send(self.buffer_to_send.get())
            self.buffer_to_send.remove(sent_count)

        def handle_close(self):
            debug(
                'connection to client %s:%i closed' % self.getsockname()
            )
            self.close()

            # if this socket to the client is closed, the one to the
            # remote host must be closed as well
            buddy = self.buddy_connection
            if buddy:
                debug("closing buddy socket %s:%i" % buddy.getsockname())
                buddy.close()
