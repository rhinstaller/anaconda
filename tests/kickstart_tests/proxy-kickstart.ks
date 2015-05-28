# Start a super-simple proxy server on localhost
# A list of proxied requests will be saved to /tmp/proxy.log
%pre --erroronfail
# Write the proxy script to a file in /tmp
cat - << "EOF" > /tmp/proxy-test.py
from six.moves import SimpleHTTPServer, socketserver
from six.moves.urllib.request import urlopen
import os, sys

import logging
log = logging.getLogger("proxy_test")
log_handler = logging.FileHandler('/tmp/proxy.log')
log.setLevel(logging.INFO)
log.addHandler(log_handler)

class ProxyHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
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
python /tmp/proxy-test.py > /dev/null 2>&1 &
%end

url --url=http://dl.fedoraproject.org/pub/fedora/linux/development/$releasever/$basearch/os/ --proxy=127.0.0.1:8080
repo --name=kstest-http --baseurl=HTTP-ADDON-REPO --proxy=127.0.0.1:8080
install
network --bootproto=dhcp

bootloader --timeout=1
zerombr
clearpart --all
autopart

keyboard us
lang en
timezone America/New_York
rootpw qweqwe
shutdown

# Install @core, which will also pull in testpkg-http-core from the addon repo
%packages
%end

%post --nochroot
# Look for the following as evidence that a proxy was used:
# a .treeinfo request
# primary.xml from the repodata
# the kernel package from the Fedora repo
# testpkg-http-core from the addon repo

if ! grep -q '\.treeinfo$' /tmp/proxy.log; then
    result='.treeinfo request was not proxied'
elif ! grep -q 'repodata/.*primary.xml' /tmp/proxy.log; then
    result='repodata requests were not proxied'
elif ! grep -q 'kernel-.*\.rpm' /tmp/proxy.log; then
    result='base repo package requests were not proxied'
elif ! grep -q 'testpkg-http-core.*\.rpm' /tmp/proxy.log; then
    result='addon repo package requests were not proxied'
else
    result='SUCCESS'
fi

# Write the result to the installed /root
echo "$result" > $ANA_INSTALL_PATH/root/RESULT
%end
