# ostreepayload.py
# Deploy OSTree trees to target
#
# Copyright (C) 2012,2014,2021  Red Hat, Inc.
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
from blivet.size import Size

from dasbus.client.proxy import get_object_path

from pyanaconda.core.constants import PAYLOAD_TYPE_RPM_OSTREE, SOURCE_TYPE_RPM_OSTREE, \
    SOURCE_TYPE_FLATPAK
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.payload.base import Payload
from pyanaconda.ui.lib.payload import get_payload, get_source, set_up_sources, create_source

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class RPMOSTreePayload(Payload):
    """ A RPMOSTreePayload deploys a tree (possibly with layered packages)
    onto the target system."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._payload_proxy = get_payload(self.type)

    def set_from_opts(self, opts):
        """Add the flatpak source if available."""
        flatpak_source = create_source(SOURCE_TYPE_FLATPAK)

        if not flatpak_source.IsAvailable():
            log.debug("The flatpak source is not available.")
            return

        sources = self.proxy.Sources
        sources.append(get_object_path(flatpak_source))
        self.proxy.SetSources(sources)

    @property
    def type(self):
        """The DBus type of the payload."""
        return PAYLOAD_TYPE_RPM_OSTREE

    def get_source_proxy(self):
        """Get the DBus proxy of the RPM source."""
        return get_source(self.proxy, SOURCE_TYPE_RPM_OSTREE)

    @property
    def source_type(self):
        """The DBus type of the source."""
        source_proxy = self.get_source_proxy()
        return source_proxy.Type

    @property
    def kernel_version_list(self):
        """Get the kernel version list."""
        return self.service_proxy.GetKernelVersionList()

    @property
    def space_required(self):
        """Get the required space."""
        return Size(self.service_proxy.CalculateRequiredSpace())

    @property
    def needs_network(self):
        """Test ostree repository if it requires network."""
        return self.service_proxy.IsNetworkRequired()

    def setup(self):
        """Set up the sources."""
        set_up_sources(self.proxy)

    def pre_install(self):
        """Run the pre-installation tasks."""
        log.debug("Nothing to do in the pre-install step.")

    def install(self):
        """Run the installation tasks."""
        task_paths = self.service_proxy.InstallWithTasks()
        self._run_tasks(task_paths, self._progress_cb)

    def post_install(self):
        """Run the post-installation tasks."""
        task_paths = self.service_proxy.PostInstallWithTasks()
        self._run_tasks(task_paths)

    def unsetup(self):
        """Tear down the sources and the payload."""
        task_paths = self.service_proxy.TeardownWithTasks()
        self._run_tasks(task_paths)

    def _run_tasks(self, task_paths, progress_cb=None):
        """Run the given remote tasks of the Payload module."""
        for task_path in task_paths:
            task_proxy = PAYLOADS.get_proxy(task_path)

            if progress_cb:
                task_proxy.ProgressChanged.connect(progress_cb)

            sync_run_task(task_proxy)
