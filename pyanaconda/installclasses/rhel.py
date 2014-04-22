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

from pyanaconda.installclass import BaseInstallClass
from pyanaconda.constants import *
from pyanaconda.product import *
from pyanaconda import network
from pyanaconda import nm
from pyanaconda import iutil
import types

class InstallClass(BaseInstallClass):
    # name has underscore used for mnemonics, strip if you dont need it
    id = "rhel"
    name = N_("Red Hat Enterprise Linux")
    sortPriority = 20000
    if not productName.startswith("Red Hat "):
        hidden = 1
    defaultFS = "xfs"

    bootloaderTimeoutDefault = 5
    bootloaderExtraArgs = []

    ignoredPackages = ["ntfsprogs", "reiserfs-utils"]

    installUpdates = False

    _l10n_domain = "comps"

    efi_dir = "redhat"

    def configure(self, anaconda):
        BaseInstallClass.configure(self, anaconda)
        BaseInstallClass.setDefaultPartitioning(self, anaconda.storage)

    # Set first boot policy regarding ONBOOT value
    # (i.e. which network devices should be activated automatically after reboot)
    # After switch root we set ONBOOT=no as default for all devices not activated
    # in initramfs. Here, at the end of installation, we check and modify it eventually.
    def setNetworkOnbootDefault(self, ksdata):
        # if there is no device to be autoactivated after reboot
        for devName in nm.nm_devices():
            if nm.nm_device_type_is_wifi(devName):
                continue
            try:
                onboot = nm.nm_device_setting_value(devName, "connection", "autoconnect")
            except nm.SettingsNotFoundError:
                continue
            if not onboot == False:
                return

        # set ONBOOT=yes for the device used during installation
        # (ie for majority of cases the one having the default route)
        devName = network.default_route_device()
        if not devName:
            return
        if nm.nm_device_type_is_wifi(devName):
            return
        ifcfg_path = network.find_ifcfg_file_of_device(devName, root_path=iutil.getSysroot())
        if not ifcfg_path:
            return
        ifcfg = network.IfcfgFile(ifcfg_path)
        ifcfg.read()
        ifcfg.set(('ONBOOT', 'yes'))
        ifcfg.write()
        for nd in ksdata.network.network:
            if nd.device == devName:
                nd.onboot = True
                break

    def __init__(self):
        BaseInstallClass.__init__(self)
