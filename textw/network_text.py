#
# network_text.py: text mode network configuration dialogs
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#
from constants_text import *
import network

class HostnameWindow:
    def __call__(self, screen, anaconda):
        hname = network.getDefaultHostname(anaconda)
        anaconda.network.hostname = hname
        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
