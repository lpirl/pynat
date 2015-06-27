#!/usr/bin/python2
# coding: UTF-8

"""
A minimal example for establishing a port forwarding.
"""

from urllib2 import urlopen

from port_forwarding import PortForwarding

# set up the port forwarding
remote_host = "duckduckgo.com"
remote_port = 80
forwarding = PortForwarding("127.0.0.1", remote_host, remote_port)
print("forwarding to %s:%i" % (remote_host, remote_port))

# see what local port is used to forward:
local_url = 'http://127.0.0.1:%i/' % forwarding.listen_port
print("local url is %s" % local_url)

# a trivial check if everything works
f = urlopen(local_url)
for line in f.readlines():
    if "<title>" in line:
        print(line.strip())
        break

# prints "<title>DuckDuckGo</title>"

# end the forwarding
forwarding.close()
