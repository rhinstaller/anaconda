#
# Copyright (C) 2020  Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import INSTALL_TREE
from pyanaconda.core.i18n import _
from pyanaconda.modules.payloads.payload.live_image.installation import InstallFromImageTask
from pyanaconda.modules.payloads.payload.live_os.utils import get_kernel_version_list
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.base import Payload
from pyanaconda.progress import progressQ

log = get_packaging_logger()

__all__ = ["BaseLivePayload"]


class BaseLivePayload(Payload):
    """Base class for live payloads."""

    # Inherit abstract methods from Payload
    # pylint: disable=abstract-method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._kernel_version_list = []

    def install(self):
        """ Install the payload. """
        task = InstallFromImageTask(
            sysroot=conf.target.system_root,
            mount_point=INSTALL_TREE + "/"
        )
        task.progress_changed_signal.connect(self._progress_cb)
        task.run()

    def post_install(self):
        """ Perform post-installation tasks. """
        progressQ.send_message(_("Performing post-installation setup tasks"))
        payload_utils.unmount(INSTALL_TREE, raise_exc=True)

        super().post_install()

    def _update_kernel_version_list(self):
        self._kernel_version_list = get_kernel_version_list(INSTALL_TREE)

    @property
    def kernel_version_list(self):
        return self._kernel_version_list
