#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
from pyanaconda.core.configuration.base import Section
from pyanaconda.core.constants import SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN


class PayloadSection(Section):
    """The Payload section."""

    @property
    def default_environment(self):
        """Default package environment."""
        return self._get_option("default_environment", str)

    @property
    def ignored_packages(self):
        """List of ignored packages.

        Anaconda flags several packages to be installed based on the configuration
        of the system -- things like fs utilities, boot loader, etc. This is a list
        of packages that we should not try to install using the aforementioned
        mechanism.
        """
        return self._get_option("ignored_packages", str).split()

    @property
    def updates_repositories(self):
        """List of names of repositories that provide latest updates.

        This option also controls whether or not Anaconda should provide
        an option to install the latest updates during installation source
        selection.

        The installation of latest updates is selected by default, if
        the closest mirror is selected, and the "updates" repo is enabled.
        """
        return self._get_option("updates_repositories", str).split()

    @property
    def enabled_repositories_from_treeinfo(self):
        """List of .treeinfo variant types to enable

        This flag controls which .treeinfo variant repos Anaconda
        will automatically enable.  For a list of valid types see
        .treeinfo documentation.
        """
        return self._get_option("enabled_repositories_from_treeinfo", str).split()

    @property
    def enable_closest_mirror(self):
        """Enable installation from the closest mirror.

        A hint if mirrors are expected to be available for the distribution
        installed by the given product. At the moment this just used to show/hide
        the "closest mirror" option in the UI.
        """
        return self._get_option("enable_closest_mirror", bool)

    @property
    def default_source(self):
        """Default installation source.

        Valid values:

        CLOSEST_MIRROR  Use closest public repository mirror.
        CDN             Use Content Delivery Network (CDN).
        """
        value = self._get_option("default_source", str)

        if value not in (SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN):
            raise ValueError("Invalid value: {}".format(value))

        return value

    @property
    def enable_ignore_broken_packages(self):
        """Enable possibility to skip packages with conflicts and broken dependencies.

        This enables --ignorebroken parameter of the packages section and related DBus API.

        If this feature is disabled Anaconda won't start the installation when
        --ignorebroken paramater is used. Instead print error message to user
        when Anaconda is started and quit the installation process.
        It will also block use of related DBus API.
        """
        return self._get_option("enable_ignore_broken_packages", bool)

    @property
    def verify_ssl(self):
        """Global option if the ssl verification is enabled.

        If disabled it prevents Anaconda from verifying the ssl certificate for all HTTPS
        connections with an exception of the additional repositories added by kickstart (where
        --noverifyssl can be set per repo). Newly created additional repositories will honor
        this option.
        """
        return self._get_option("verify_ssl", bool)

    @property
    def default_rpm_gpg_keys(self):
        """List of GPG keys to import into RPM database at end of installation."""
        return self._get_option("default_rpm_gpg_keys", str).split()
