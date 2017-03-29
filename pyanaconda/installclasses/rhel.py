#
# rhel.py
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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

import os
import logging
log = logging.getLogger("anaconda")

from pyanaconda.installclass import BaseInstallClass
from pyanaconda.product import productName
from pyanaconda import network
from pyanaconda import nm
from pyanaconda import iutil
from pyanaconda.kickstart import getAvailableDiskSpace
from pyanaconda.flags import flags
from blivet.partspec import PartSpec
from blivet.platform import platform
from blivet.devicelibs import swap
from blivet.size import Size

class RHELBaseInstallClass(BaseInstallClass):
    name = "Red Hat Enterprise Linux"
    sortPriority = 20000
    if not productName.startswith("Red Hat "):
        hidden = True
    defaultFS = "xfs"

    bootloaderTimeoutDefault = 5

    ignoredPackages = ["ntfsprogs", "reiserfs-utils", "hfsplus-tools"]

    installUpdates = False

    _l10n_domain = "comps"

    efi_dir = "redhat"

    help_placeholder = "RHEL7Placeholder.html"
    help_placeholder_with_links = "RHEL7PlaceholderWithLinks.html"

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)

    def setNetworkOnbootDefault(self, ksdata):
        if any(nd.onboot for nd in ksdata.network.network if nd.device):
            return
        # choose the device used during installation
        # (ie for majority of cases the one having the default route)
        dev = network.default_route_device() \
              or network.default_route_device(family="inet6")
        if not dev:
            return
        # ignore wireless (its ifcfgs would need to be handled differently)
        if nm.nm_device_type_is_wifi(dev):
            return
        network.update_onboot_value(dev, True, ksdata=ksdata)

    def __init__(self):
        BaseInstallClass.__init__(self)

class RHELAtomicInstallClass(RHELBaseInstallClass):
    name = "Red Hat Enterprise Linux Atomic Host"
    sortPriority=21000
    hidden = not productName.startswith(("RHEL Atomic Host", "Red Hat Enterprise Linux Atomic"))

    def __init__(self):
        self.localemap = {} # loaded lazily
        RHELBaseInstallClass.__init__(self)

    def setDefaultPartitioning(self, storage):
        autorequests = [PartSpec(mountpoint="/", fstype=storage.defaultFSType,
                                size=Size("1GiB"), maxSize=Size("3GiB"), grow=True, lv=True)]

        bootreqs = platform.setDefaultPartitioning()
        if bootreqs:
            autorequests.extend(bootreqs)

        disk_space = getAvailableDiskSpace(storage)
        swp = swap.swapSuggestion(disk_space=disk_space)
        autorequests.append(PartSpec(fstype="swap", size=swp, grow=False,
                                    lv=True, encrypted=True))

        for autoreq in autorequests:
            if autoreq.fstype is None:
                if autoreq.mountpoint == "/boot":
                    autoreq.fstype = storage.defaultBootFSType
                    autoreq.size = Size("300MiB")
                else:
                    autoreq.fstype = storage.defaultFSType

        storage.autoPartitionRequests = autorequests

    def filterSupportedLangs(self, ksdata, langs):
        self._initialize_localemap(ksdata.ostreesetup.ref,
                                   ksdata.ostreesetup.url)
        for lang in langs:
            if lang in self.localemap:
                yield lang

    def filterSupportedLocales(self, ksdata, lang, locales):
        self._initialize_localemap(ksdata.ostreesetup.ref,
                                   ksdata.ostreesetup.url)
        supported = []
        if lang in self.localemap:
            for locale in locales:
                stripped = self._strip_codeset_and_modifier(locale)
                if stripped in self.localemap[lang]:
                    supported.append(locale)
        return supported

    def _initialize_localemap(self, ref, repo):

        if self.localemap:
            return

        # fallback to just en_US in case of errors
        self.localemap = { "en": ["en_US"] }

        # Let's only handle local embedded repos for now. Anyway, it'd probably
        # not be very common to only override ostreesetup through kickstart and
        # still want the interactive installer. Though to be nice, let's handle
        # that case.
        if not repo.startswith("file://"):
            log.info("ostree repo is not local; defaulting to en_US")
            return

        # convert to regular UNIX path
        repo = repo[len("file://"):]

        iutil.mkdirChain(os.path.join(repo, "tmp/usr/lib"))
        rc = iutil.execWithRedirect("/usr/bin/ostree",
            ["checkout", "--repo", repo, ref,
             "--subpath", "/usr/lib/locale/locale-archive",
             "install/ostree/tmp/usr/lib/locale"])
        if rc != 0:
            log.error("failed to check out locale-archive; check program.log")
            return

        for line in iutil.execReadlines("/usr/bin/localedef",
                                        ["--prefix", os.path.join(repo, "tmp"),
                                         "--list-archive"]):
            line = self._strip_codeset_and_modifier(line)
            (lang, territory) = line.split('_')
            if lang not in self.localemap:
                self.localemap[lang] = [line]
            else:
                self.localemap[lang].append(line)

    @staticmethod
    def _strip_codeset_and_modifier(locale):
        if '@' in locale:
            locale = locale[:locale.find('@')]
        if '.' in locale:
            locale = locale[:locale.find('.')]
        return locale
