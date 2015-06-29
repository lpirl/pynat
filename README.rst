pynat
=====

DNAT port forwarding in pure Python

* asynchronous (uses non-blocking `asyncore <https://docs.python.org/2/library/asyncore.html>`_ library)
* no dependencies
* compatible with PyPy

use case
--------

* you need to forward ports from the executing machine to another hosts

  * e.g. you want to temporarily forward SSH to a NATed host through a
    Web server

* your application is multi-processed and it cannot be guaranteed that a
  process that created a port forwarding also closes it (but another
  process will do it)

  * this is true for most Web applications

* you don't want to grant you application rights to use ``iptables`` etc.

  * this would probably make the deployment less joyful and less secure

* you prefer few dependencies

examples
--------

`a simple example <example_simple_port_forwarding_and_test.py>`_
including a test if the forwarding works

`terminated the forwarding from within another process
<example_terminate_from_within_another_process.py>`_

todo
----

* a wrapper to conveniently set up a "process-agnostic" port forwarding
  (e.g. API as ``PortForwarding`` but returning the local port, the UNIX
  socket path and the secret)

  * thereby declutter `this example
    <example_terminate_from_within_another_process.py>`_

* ability to close established connections

feedback
--------

Feel very free to contact me via issues/email etc.
I'd be happy to hear if this actually works well in production/under load
(sadly, my use cased vanished as I left the project I developed this for).
