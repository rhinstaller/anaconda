# Start a super-simple proxy server on localhost
# A list of proxied requests will be saved to /tmp/proxy.log
%pre --erroronfail
# Write the proxy script to a file in /tmp
cat - << "EOF" > /tmp/proxy-test.py
from http.server import SimpleHTTPRequestHandler
import socketserver
from urllib.request import urlopen
import os, sys

import logging
log = logging.getLogger("proxy_test")
log_handler = logging.FileHandler('/tmp/proxy.log')
log.setLevel(logging.INFO)
log.addHandler(log_handler)

class ProxyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
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
