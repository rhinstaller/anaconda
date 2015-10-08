#!/usr/bin/python3

# Start a super-simple proxy server on localhost
# A list of proxied requests will be saved to /tmp/proxy.log

# Ignore any interruptible calls
# pylint: disable=interruptible-system-call

from http.server import SimpleHTTPRequestHandler
import socket
import select
import socketserver
from urllib.request import urlopen
import os
from base64 import b64decode

import logging
log = logging.getLogger("proxy_test")
log_handler = logging.FileHandler('/tmp/proxy.log')
log.setLevel(logging.INFO)
log.addHandler(log_handler)

class ProxyHandler(SimpleHTTPRequestHandler):
    def send_authenticate(self):
        self.send_response(407)
        self.send_header('Proxy-Authenticate', 'Basic realm=proxy-test')
        self.end_headers()

    def authenticate(self):
        # If there is no /tmp/proxy.password file, anything goes
        if not os.path.exists('/tmp/proxy.password'):
            return True

        # If there is no Authorization header, send a 407, Proxy authentication required
        authorization = self.headers['Proxy-Authorization']
        if not authorization:
            self.send_authenticate()
            return False

        # Parse the Authorization header. It should be "Basic" followed
        # user:pass encoded in base64
        if not authorization.startswith('Basic'):
            self.send_authenticate()
            return False

        try:
            client_auth = b64decode(authorization.split()[1])
        except IndexError:
            self.send_authenticate()
            return False

        with open('/tmp/proxy.password', 'rb') as f:
            server_auth = f.readline().strip()

        if client_auth != server_auth:
            self.send_authenticate()
            return False

        return True

    def do_GET(self):
        if not self.authenticate():
            return

        # Log the path then proxy the request via urllib
        log.info(self.path)
        data = urlopen(self.path).read()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_CONNECT(self):
        if not self.authenticate():
            return

        # In this case self.path is just a host:port pair instead
        # of a URL.
        host, port = self.path.split(':')

        # Open a socket to the requested location
        target = socket.create_connection((host, port))

        # Report that the connection is established
        self.send_response(200)
        self.end_headers()

        # Forward data in either direction as it comes in, until
        # someone closes the connection
        host_fd = self.rfile.fileno()
        target_fd = target.fileno()
        bufsize = 1024
        check_fds = [host_fd, target_fd]

        while True:
            readfds, _writefds, xfds = select.select(check_fds, [], check_fds)
            if xfds:
                break

            if host_fd in readfds:
                buf = os.read(host_fd, bufsize)
                if not buf:
                    break

                target.send(buf)

            if target_fd in readfds:
                buf = os.read(target_fd, bufsize)
                if not buf:
                    break

                self.wfile.write(buf)

        target.close()

class ProxyServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self):
        socketserver.TCPServer.__init__(self, ('', 8080), ProxyHandler)

ProxyServer().serve_forever()
