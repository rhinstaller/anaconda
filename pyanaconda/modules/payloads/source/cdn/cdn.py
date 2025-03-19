#
# Kickstart module for CDN payload source.
#
# Copyright (C) 2020 Red Hat, Inc.
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
from pyanaconda.core.i18n import _
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.cdn.initialization import SetUpCDNSourceTask
from pyanaconda.modules.payloads.source.repo_files.repo_files import RepoFilesSourceModule
from pyanaconda.modules.payloads.source.cdn.cdn_interface import CDNSourceInterface
from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


class CDNSourceModule(RepoFilesSourceModule):
    """The CDN source payload module."""

    def __repr__(self):
        return "Source(type='CDN')"

    def for_publication(self):
        """Get the interface used to publish this source."""
        return CDNSourceInterface(self)

    @property
    def type(self):
        """Get type of this source."""
        return SourceType.CDN

    @property
    def description(self):
        """Get description of this source."""
        return _("Red Hat CDN")

    def set_up_with_tasks(self):
        """Set up the installation source.

        :return [Task]: a list of tasks
        """
        return [SetUpCDNSourceTask()]
