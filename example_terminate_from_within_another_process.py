#!/usr/bin/python2 -O
# coding: UTF-8

"""
An example where the establishing and terminating process of a port
forwarding are not the same.

For example, this can happen in Web applications where the Web server
uses multiple processes to handle requests.
"""

from uuid import uuid4
from urllib2 import urlopen
from multiprocessing import Process, Queue
from socket import socket, AF_UNIX, SOCK_STREAM, error as socket_error
from tempfile import mktemp

from pynat import PortForwarding
from pynat import PortForwardingTerminator
from pynat.util import port_is_open, wait_for_all_child_threads

def establising_process(queue):
    """
    Sets up a port forwarding and a corresponding terminator
    (that lives in the same process and thereby can close the socket
    of the port forwarding later on).

    Puts the local port used, the UNIX socket path and the secret that
    is needed to close the socket of the port forwarding from within other
    processes into the ``queue``.
    """
    forwarding = PortForwarding("127.0.0.1", "example.com", 80)

    # can be any string:
    close_secret = str(uuid4())

    close_socket_path = mktemp(prefix="pynat_terminator")

    PortForwardingTerminator(close_socket_path, close_secret, forwarding)

    queue.put(forwarding.listen_port)
    queue.put(close_socket_path)
    queue.put(close_secret)
    queue.close()

    # We have to keep this thread alive until the port forwarding is
    # closed
    # (in a less artificial setting, it probably not required to do this
    # explicitly).
    wait_for_all_child_threads()

def terminating_process(close_socket_path, close_secret):
    """
    Sends the ``close_secret`` through the unix socket at
    ``close_socket_path`` into the ``establising process`` to close the
    socket of the port forwarding.
    """
    my_socket = socket(AF_UNIX, SOCK_STREAM)
    try:
        my_socket.connect(close_socket_path)
    except socket_error:
        print "ERROR: could not connect to socket %s" % close_socket_path
        exit(1)
    my_socket.sendall(close_secret)
    my_socket.close()


queue = Queue()

# create a port forwarding
# (e.g. this could be a backend process that writes the UNIX socket and
# the secret to a database)
p1 = Process(target=establising_process, args=(queue,))
p1.start()

listen_port = queue.get()

# get the UNIX socket and the secret required to terminate the port
# forwarding:
close_socket_path = queue.get()
close_secret = queue.get()

# … do something with the port forwarding …
print "forwaring works before closing it:", \
        port_is_open("127.0.0.1", listen_port)

# terminate the forwarding
# (e.g. this could be some Web server process that retrieves the UNIX
# socket and the secret from a database)
p2 = Process(target=terminating_process,
             args=(close_socket_path, close_secret))
p2.start()
p2.join()
p1.join()

print "forwaring active after closing it:", \
        port_is_open("127.0.0.1", listen_port)
