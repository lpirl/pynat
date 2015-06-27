pynat
=====

asynchronous DNAT port forwarding in pure Python

status
------

The code exists, I just have to review it for publication.

examples
--------

a simple example
................

…including a test if the forwarding works:

.. include:: examples/simple_port_forwarding_and_test.py
    :code: python
    :start-line: 10

terminated the forwarding from within another process
.....................................................

.. include:: examples/terminate_from_within_another_process.py
    :code: python
    :start-line: 10
