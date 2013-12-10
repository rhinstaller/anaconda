# Abstract base classes for UI classes
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Shea <dshea@redhat.com
#

# This file contains abstract base classes that provide specific functionality
# that can be added to another class. The idea is sort-of modelled after Java's
# interfaces. An abstract base class cannot be instatiated, and it provides a
# contract for classes that inherit from it: any method or property marked as
# abstract in the base class must be overriden in the inheriting class. This
# allows for cleaner implementation of certain types of mixin-classes: a class
# that adds functionality to another class can explicitly require that methods
# or properties be provided by the inheriting class or another superclass of
# the inheriting class.
#
# In general, classes that inherit from abstract base classes should place the
# abstract base class at the end of the inheritance list. This way any abstract
# methods or properties in the abc will be overridden by the base classes
# that are first in the inheritance list. For example, an abstract base class
# may add a method that reads from Spoke.data:
#
#    class Mixin(object):
#        __metaclass__ = ABCMeta
#
#        @abstractproperty
#        def data(self):
#            pass
#
#        def isHD(self):
#            return self.data.method == "harddrive"
#
# The Mixin class will add the method isHD to any class that inherits from it,
# and classes that inherit from Mixin must provide a data property.
#
#    class MixedObject(UIObject, Mixin):
#        ....
#
# The method resolution order of MixedObject resolves UIObject.data before
# Mixin.data, so UIObject.data satisfies the requirment that Mixin.data be
# overriden.

from abc import ABCMeta, abstractproperty

from pyanaconda import constants
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.communication import hubQ
from pyanaconda.i18n import _

import logging
import copy

class StorageChecker(object):
    __metaclass__ = ABCMeta

    log = logging.getLogger("anaconda")
    errors = []
    warnings = []

    def __init__(self, mainSpokeClass="StorageSpoke"):
        self._mainSpokeClass = mainSpokeClass

    @abstractproperty
    def storage(self):
        pass

    def run(self):
        threadMgr.add(AnacondaThread(name=constants.THREAD_CHECK_STORAGE,
                                     target=self.checkStorage))

    def checkStorage(self):
        threadMgr.wait(constants.THREAD_EXECUTE_STORAGE)

        hubQ.send_not_ready(self._mainSpokeClass)
        hubQ.send_message(self._mainSpokeClass, _("Checking storage configuration..."))
        (StorageChecker.errors,
         StorageChecker.warnings) = self.storage.sanityCheck()
        hubQ.send_ready(self._mainSpokeClass, True)
        for e in StorageChecker.errors:
            self.log.error(e)
        for w in StorageChecker.warnings:
            self.log.warn(w)

class SourceSwitchHandler(object):
    """ A class that can be used as a mixin handling
    installation source switching.
    It will correctly switch to the new method
    and cleanup any previous method set.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def data(self):
        pass

    @abstractproperty
    def storage(self):
        pass

    def __init__(self):
        self._device = None
        self._current_iso_path = None

    def _clean_hdd_iso(self):
        """ Clean HDD ISO usage
        This means unmounting the partition and unprotecting it,
        so it can be used for the installation.
        """
        if self.data.method.method == "harddrive" and self.data.method.partition:
            part = self.data.method.partition
            dev = self.storage.devicetree.getDeviceByName(part)
            if dev:
                dev.protected = False
            self.storage.config.protectedDevSpecs.remove(part)

    def set_source_hdd_iso(self, device, iso_path):
        """ Switch to the HDD ISO install source
        :param partition: name of the partition hosting the ISO
        :type partition: string
        :param iso_path: full path to the source ISO file
        :type iso_path: string
        """
        partition = device.name
        # the GUI source spoke also does the copy
        old_source = copy.copy(self.data.method)

        # if a different partition was used previously, unprotect it
        if old_source.method == "harddrive" and old_source.partition != partition:
            self._clean_hdd_iso()

        # protect current device
        if device:
            device.protected = True
            self.storage.config.protectedDevSpecs.append(device.name)

        self.data.method.method = "harddrive"
        self.data.method.partition = partition
        # the / gets stripped off by payload.ISOImage
        self.data.method.dir = "/" + iso_path

        # as we already made the device protected when
        # switching to it, we don't need to protect it here

    def set_source_url(self, url=None):
        """ Switch to install source specified by URL """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "url"
        if url is not None:
            self.data.method.url = url

    def set_source_nfs(self, opts=None):
        """ Switch to NFS install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "nfs"
        if opts is not None:
            self.data.method.opts = opts

    def set_source_cdrom(self):
        """ Switch to cdrom install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = "cdrom"

    def set_source_closest_mirror(self):
        """ Switch to the closest mirror install source """
        # clean any old HDD ISO sources
        self._clean_hdd_iso()

        self.data.method.method = None
