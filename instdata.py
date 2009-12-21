#
# instdata.py - central store for all configuration data needed to install
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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
# Author(s): Erik Troan <ewt@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#

import os, sys
import stat
import string
import firewall
import timezone
import booty
import storage
import urllib
import iutil
import isys
import shlex
from flags import *
from constants import *
from simpleconfig import SimpleConfigFile

import logging
log = logging.getLogger("anaconda")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

# Collector class for all data related to an install/upgrade.

class InstallData:

    def reset(self):
        # Reset everything except:
        #
        # - The install language

        self.storage = storage.Storage(self.anaconda)
        self.bootloader = booty.getBootloader(self)
        self.escrowCertificates = {}

        if iutil.isS390() or self.anaconda.ksdata:
            self.firstboot = FIRSTBOOT_SKIP
        else:
            self.firstboot = FIRSTBOOT_DEFAULT

    def writeKS(self, f):
        self.bootloader.writeKS(f)
        self.storage.writeKS(f)

    def __init__(self, anaconda, extraModules):
        self.anaconda = anaconda
        self.extraModules = extraModules
        self.simpleFilter = True

        self.reset()
