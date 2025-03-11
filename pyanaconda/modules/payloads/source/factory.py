#
# Factory class to create sources.
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
from pyanaconda.modules.payloads.constants import SourceType
from pyanaconda.modules.payloads.source.utils import is_tar

__all__ = ["SourceFactory"]


class SourceFactory:
    """Factory to create payload sources."""

    @staticmethod
    def create_source(source_type: SourceType):
        """Create a source module.

        :param source_type: a source type
        :return: a source module
        """
        if source_type == SourceType.LIVE_OS_IMAGE:
            from pyanaconda.modules.payloads.source.live_os.live_os import (
                LiveOSSourceModule,
            )
            return LiveOSSourceModule()
        elif source_type == SourceType.LIVE_IMAGE:
            from pyanaconda.modules.payloads.source.live_image.live_image import (
                LiveImageSourceModule,
            )
            return LiveImageSourceModule()
        elif source_type == SourceType.LIVE_TAR:
            from pyanaconda.modules.payloads.source.live_tar.live_tar import (
                LiveTarSourceModule,
            )
            return LiveTarSourceModule()
        elif source_type == SourceType.CDROM:
            from pyanaconda.modules.payloads.source.cdrom.cdrom import CdromSourceModule
            return CdromSourceModule()
        elif source_type == SourceType.HMC:
            from pyanaconda.modules.payloads.source.hmc.hmc import HMCSourceModule
            return HMCSourceModule()
        elif source_type == SourceType.REPO_FILES:
            from pyanaconda.modules.payloads.source.repo_files.repo_files import (
                RepoFilesSourceModule,
            )
            return RepoFilesSourceModule()
        elif source_type == SourceType.REPO_PATH:
            from pyanaconda.modules.payloads.source.repo_path.repo_path import (
                RepoPathSourceModule,
            )
            return RepoPathSourceModule()
        elif source_type == SourceType.NFS:
            from pyanaconda.modules.payloads.source.nfs.nfs import NFSSourceModule
            return NFSSourceModule()
        elif source_type == SourceType.URL:
            from pyanaconda.modules.payloads.source.url.url import URLSourceModule
            return URLSourceModule()
        elif source_type == SourceType.HDD:
            from pyanaconda.modules.payloads.source.harddrive.harddrive import (
                HardDriveSourceModule,
            )
            return HardDriveSourceModule()
        elif source_type == SourceType.CDN:
            from pyanaconda.modules.payloads.source.cdn.cdn import CDNSourceModule
            return CDNSourceModule()
        elif source_type == SourceType.CLOSEST_MIRROR:
            from pyanaconda.modules.payloads.source.closest_mirror.closest_mirror import (
                ClosestMirrorSourceModule,
            )
            return ClosestMirrorSourceModule()
        elif source_type == SourceType.RPM_OSTREE:
            from pyanaconda.modules.payloads.source.rpm_ostree.rpm_ostree import (
                RPMOSTreeSourceModule,
            )
            return RPMOSTreeSourceModule()
        elif source_type == SourceType.RPM_OSTREE_CONTAINER:
            from pyanaconda.modules.payloads.source.rpm_ostree_container.rpm_ostree_container import (
                RPMOSTreeContainerSourceModule,
            )
            return RPMOSTreeContainerSourceModule()
        elif source_type == SourceType.FLATPAK:
            from pyanaconda.modules.payloads.source.flatpak.flatpak import (
                FlatpakSourceModule,
            )
            return FlatpakSourceModule()

        raise ValueError("Unknown source type: {}".format(source_type))

    @staticmethod
    def get_rpm_type_for_kickstart(ks_data):
        """Generate source type from DNF kickstart data.

        This method will mimic behavior of method command which will take first from the list
        and ignore rest of the commands. If we want to improve this behavior we should do that
        in the pykickstart instead.

        :param ks_data: kickstart data from DNF payload
        :return: SourceType value
        """
        if ks_data.cdrom.seen:
            return SourceType.CDROM
        if ks_data.harddrive.seen:
            return SourceType.HDD
        if ks_data.nfs.seen:
            return SourceType.NFS
        if ks_data.url.seen:
            return SourceType.URL
        if ks_data.hmc.seen:
            return SourceType.HMC

        return None

    @staticmethod
    def get_rpm_ostree_type_for_kickstart(ks_data):
        """Generate source type from RPM OSTree kickstart data.

        :param ks_data: kickstart data from DNF payload
        :return: SourceType value
        """
        if ks_data.ostreecontainer.seen:
            return SourceType.RPM_OSTREE_CONTAINER
        if ks_data.ostreesetup.seen:
            return SourceType.RPM_OSTREE

        return None

    @staticmethod
    def get_live_image_type_for_kickstart(ks_data):
        """Generate source type from live image kickstart data.

        :param ks_data: kickstart data from DNF payload
        :return: SourceType value
        """
        if ks_data.liveimg.seen:
            if is_tar(ks_data.liveimg.url):
                return SourceType.LIVE_TAR
            else:
                return SourceType.LIVE_IMAGE

        return None
