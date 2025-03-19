# Entry point for anaconda's software management module.
#
# Copyright (C) 2019  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from abc import ABCMeta, abstractmethod

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

__all__ = ["Payload"]


class Payload(metaclass=ABCMeta):
    """Payload is an abstract class for OS install delivery methods."""
    def __init__(self, data):
        """Initialize Payload class

        :param data: This param is a kickstart.AnacondaKSHandler class.
        """
        self.data = data

        # A DBus proxy of the payload.
        self._payload_proxy = None

    def set_from_opts(self, opts):
        """Set the payload from the Anaconda cmdline options.

        :param opts: a namespace of options
        """
        pass

    @property
    @abstractmethod
    def type(self):
        """The DBus type of the payload."""
        return None

    @property
    def proxy(self):
        """The DBus proxy of the DNF module.

        :return: a DBus proxy
        """
        return self._payload_proxy

    def get_source_proxy(self):
        """Get the DBus proxy of the installation source (if any).

        There may be payloads that do not have an installation source
        and thus also no source proxy. It is still beter to define
        this method also for those payloads and have it return None.

        :return: a DBus proxy or None
        """
        return None

    @property
    def source_type(self):
        """The DBus type of the source."""
        return None

    def is_ready(self):
        """Is the payload ready?"""
        return True

    def setup(self):
        """Do any payload-specific setup."""
        pass

    def unsetup(self):
        """Invalidate a previously setup payload."""
        pass

    @property
    def needs_network(self):
        return False

    ###
    # METHODS FOR QUERYING STATE
    ###
    @property
    def space_required(self):
        """The total disk space (Size) required for the current selection."""
        raise NotImplementedError()

    @property
    def kernel_version_list(self):
        """An iterable of the kernel versions installed by the payload."""
        raise NotImplementedError()

    ###
    # METHODS FOR INSTALLING THE PAYLOAD
    ###
    def pre_install(self):
        """Perform pre-installation tasks."""
        from pyanaconda.modules.payloads.base.initialization import PrepareSystemForInstallationTask
        PrepareSystemForInstallationTask(conf.target.system_root).run()

    def install(self):
        """Install the payload."""
        raise NotImplementedError()

    def post_install(self):
        """Perform post-installation tasks."""

        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here
        from pyanaconda.modules.payloads.base.initialization import CopyDriverDisksFilesTask
        CopyDriverDisksFilesTask(conf.target.system_root).run()
