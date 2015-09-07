#!/usr/bin/python3
#
# httpd.py - Simple http server
#
# Copyright (C) 2015  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): David Shea <dshea@redhat.com>
#

# Usage: httpd.py <directory>
# If all goes well, it will print the port number it is listening and the child process PID,
# and then fork to the background and exit from the parent.

from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys
import os

if len(sys.argv) != 2:
    print("Usage: httpd.py <directory>", file=sys.stderr)
    sys.exit(1)

# Bind to any free port
server = HTTPServer(('', 0), SimpleHTTPRequestHandler)

# Fork to the background
pid = os.fork()
if pid == 0:
    # chdir to the directory to serve from
    os.chdir(sys.argv[1])

    # dup the standard file descriptors to /dev/null
    # pylint: disable=interruptible-system-call, ignorable-system-call
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)

    server.serve_forever()

# Print the port and the PID to stdout
print("%d %d" % (server.server_port, pid))

# That's it
sys.exit(0)
