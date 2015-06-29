# coding: UTF-8

from socket import socket, AF_INET, SOCK_STREAM
from threading import enumerate as enumerate_threads, current_thread

def port_is_open(host, port):
    return socket(AF_INET, SOCK_STREAM).connect_ex((host, port)) == 0

def wait_for_all_child_threads():
    threads = enumerate_threads()
    threads.remove(current_thread())
    for thread in threads:
        thread.join()
