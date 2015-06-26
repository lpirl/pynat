# coding: utf-8

"""
To be able to close a socket (``S1``) of a process (``P``) from within
another process, we listen on a UNIX socket (``S2``) in the same process
(``P``) and close all sockets (``S1`` and ``S2``) upon receiving a
pre-shared secret.

UNIX socked addresses can be easily serialized and thereby shared between
processes, stored in a file, a database etc.
"""

from os import remove

from socket import SOCK_STREAM, AF_UNIX
from asyncore import dispatcher, loop

from logging import debug

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
