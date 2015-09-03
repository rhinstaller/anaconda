# Start a super-simple proxy server on localhost
# A list of proxied requests will be saved to /tmp/proxy.log
%pre --erroronfail
# Write the proxy script to a file in /tmp
cat - << "EOF" > /tmp/proxy-test.py
from http.server import SimpleHTTPRequestHandler
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

class ProxyServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self):
        socketserver.TCPServer.__init__(self, ('', 8080), ProxyHandler)

ProxyServer().serve_forever()
EOF

# Run the server in the background and exit
python3 /tmp/proxy-test.py > /dev/null 2>&1 &
%end
