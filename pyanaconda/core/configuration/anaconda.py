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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Vendula Poncova <vponcova@redhat.com>
#
import os
import warnings

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.bootloader import BootloaderSection, BootloaderType
from pyanaconda.core.configuration.license import LicenseSection
from pyanaconda.core.configuration.network import NetworkSection
from pyanaconda.core.configuration.payload import PayloadSection
from pyanaconda.core.configuration.security import SecuritySection
from pyanaconda.core.configuration.storage import StorageSection
from pyanaconda.core.configuration.storage_constraints import StorageConstraints
from pyanaconda.core.configuration.system import SystemType, SystemSection
from pyanaconda.core.configuration.target import TargetType, TargetSection
from pyanaconda.core.configuration.base import Section, Configuration, ConfigurationError
from pyanaconda.core.configuration.profile import ProfileLoader
from pyanaconda.core.configuration.ui import UserInterfaceSection
from pyanaconda.core.constants import ANACONDA_CONFIG_TMP, ANACONDA_CONFIG_DIR

log = get_module_logger(__name__)

__all__ = ["conf", "AnacondaConfiguration"]


class AnacondaSection(Section):
    """The Anaconda section."""

    @property
    def debug(self):
        """Run Anaconda in the debugging mode."""
        return self._get_option("debug", bool)

    @property
    def activatable_modules(self):
        """List of Anaconda DBus modules that can be activated.

        Supported patterns:

            MODULE.PREFIX.*
            MODULE.NAME

        :return: a list of patterns
        """
        return self._get_deprecated_activatable_modules() \
            or self._get_option("activatable_modules").split()

    def _get_deprecated_activatable_modules(self):
        """Get a list of deprecated activatable modules.

        FIXME: This is a temporary workaround.

        If the kickstart_modules option is defined in the configuration,
        allow to activate only the specified modules and Anaconda addons.
        """
        if not self._has_option("kickstart_modules"):
            return []

        warnings.warn(
            "The kickstart_modules configuration option is deprecated and "
            "will be removed in in the future.", DeprecationWarning
        )

        return self._get_option("kickstart_modules").split() \
            + ["org.fedoraproject.Anaconda.Addons.*"]

    @property
    def forbidden_modules(self):
        """List of Anaconda DBus modules that are not allowed to run.

        Supported patterns:

            MODULE.PREFIX.*
            MODULE.NAME

        :return: a list of patterns
        """
        return self._get_deprecated_forbidden_modules() \
            + self._get_option("forbidden_modules").split()

    def _get_deprecated_forbidden_modules(self):
        """Get a list of deprecated forbidden modules.

        FIXME: This is a temporary workaround.

        If the addons_enabled option is defined in the configuration
        and set to False, don't allow to activate Anaconda addons.
        """
        if not self._has_option("addons_enabled"):
            return []

        warnings.warn(
            "The addons_enabled configuration option is deprecated and "
            "will be removed in in the future.", DeprecationWarning
        )

        if self._get_option("addons_enabled", bool):
            return []

        return ["org.fedoraproject.Anaconda.Addons.*"]

    @property
    def optional_modules(self):
        """List of Anaconda DBus modules that can fail to run.

        The installation won't be aborted because of them.

        Supported patterns:

            MODULE.PREFIX.*
            MODULE.NAME

        :return: a list of patterns
        """
        return self._get_option("optional_modules").split()

    @property
    def save_input_kickstart(self):
        return self._get_option("save_input_kickstart")

    @property
    def save_output_kickstart(self):
        return self._get_option("save_output_kickstart")

    @property
    def save_logs(self):
        return self._get_option("save_logs")


class AnacondaConfiguration(Configuration):
    """Representation of the Anaconda configuration."""

    @classmethod
    def from_defaults(cls):
        """Get the default Anaconda configuration.

        :return: an instance of AnacondaConfiguration
        """
        config = cls()
        config.set_from_defaults()
        return config

    def __init__(self):
        """Initialize the configuration."""
        super().__init__()
        self._anaconda = AnacondaSection(
            "Anaconda", self.get_parser()
        )
        self._system = SystemSection(
            "Installation System", self.get_parser()
        )
        self._target = TargetSection(
            "Installation Target", self.get_parser()
        )
        self._network = NetworkSection(
            "Network", self.get_parser()
        )
        self._payload = PayloadSection(
            "Payload", self.get_parser()
        )
        self._bootloader = BootloaderSection(
            "Bootloader", self.get_parser()
        )
        self._storage = StorageSection(
            "Storage", self.get_parser()
        )
        self._storage_constraints = StorageConstraints(
            "Storage Constraints", self.get_parser()
        )
        self._security = SecuritySection(
            "Security", self.get_parser()
        )
        self._ui = UserInterfaceSection(
            "User Interface", self.get_parser()
        )
        self._license = LicenseSection(
            "License", self.get_parser()
        )

    @property
    def anaconda(self):
        """The Anaconda section."""
        return self._anaconda

    @property
    def system(self):
        """The Installation System section."""
        return self._system

    @property
    def target(self):
        """The Installation Target section."""
        return self._target

    @property
    def network(self):
        """The Network section."""
        return self._network

    @property
    def payload(self):
        """The Payload section."""
        return self._payload

    @property
    def bootloader(self):
        """The Bootloader section."""
        return self._bootloader

    @property
    def storage(self):
        """The Storage section."""
        return self._storage

    @property
    def storage_constraints(self):
        """The Storage Constraints section."""
        return self._storage_constraints

    @property
    def security(self):
        """The Security section."""
        return self._security

    @property
    def ui(self):
        """The User Interface section."""
        return self._ui

    @property
    def license(self):
        """The License section."""
        return self._license

    def set_from_defaults(self):
        """Set the configuration from the default configuration files.

        Read the current configuration from the temporary config file.
        Or load the default configuration file from:

            /etc/anaconda/anaconda.conf

        """
        path = os.environ.get("ANACONDA_CONFIG_TMP", ANACONDA_CONFIG_TMP)

        if not path or not os.path.exists(path):
            path = os.path.join(ANACONDA_CONFIG_DIR, "anaconda.conf")

        self.read(path)
        self.validate()

    def set_from_profile(self, profile_id):
        """Set the configuration from the requested profile configuration files.

        We will use configuration files of a profile requested by the user.
        The configuration files are loaded from /etc/anaconda/profile.d.

        :param str profile_id: an id of the requested profile
        """
        loader = self._get_profile_loader()
        self._set_from_profile(loader, profile_id)

    def set_from_detected_profile(self, os_id, variant_id=None):
        """Set the configuration from the detected profile configuration files.

        We will detect the profile by matching the provided os-release values.
        The configuration files are loaded from /etc/anaconda/profile.d.

        :param str os_id: an id of the operating system or None
        :param str variant_id: an id of a specific variant of the operating system or None
        """
        loader = self._get_profile_loader()
        profile_id = loader.detect_profile(os_id, variant_id)

        if profile_id:
            self._set_from_profile(loader, profile_id)
        else:
            log.warning(
                "Unable to find any suitable configuration files for the detected "
                "os-release values. No profile configuration will be used."
            )

    def _get_profile_loader(self):
        """Load data about the available profile configuration files.

        :return: a profile loader
        """
        loader = ProfileLoader()
        loader.load_profiles(os.path.join(ANACONDA_CONFIG_DIR, "profile.d"))
        return loader

    def _set_from_profile(self, loader, profile_id):
        """Set the configuration from the profile configuration files.

        :param loader: a profile loader
        :param profile_id: an of the requested profile
        """
        # Make sure that the selected profile is valid.
        if not loader.check_profile(profile_id):
            raise ConfigurationError(
                "Unable to find any suitable configuration files "
                "for the '{}' profile.".format(profile_id)
            )

        # Read the configuration files of the profile.
        log.info("Load the '%s' profile configuration.", profile_id)
        config_paths = loader.collect_configurations(profile_id)

        for config_path in config_paths:
            self.read(config_path)

        self.validate()

    def set_from_files(self, paths=None):
        """Set the configuration from the given files and directories.

        By default, read configuration files from:

            /etc/anaconda/conf.d/

        :param paths: a list of paths to files and directories
        """
        if not paths:
            paths = [os.path.join(ANACONDA_CONFIG_DIR, "conf.d")]

        for path in paths:
            if not path or not os.path.exists(path):
                continue

            if os.path.isdir(path):
                self.read_from_directory(path)
            else:
                self.read(path)

        self.validate()

    def set_from_opts(self, opts):
        """Set the configuration from the Anaconda cmdline options.

        This code is too related to the Anaconda cmdline options, so it shouldn't
        be part of this class. We should find a better, more universal, way to change
        the Anaconda configuration.

        FIXME: This is a temporary solution.

        :param opts: a namespace of options
        """
        if opts.debug:
            self.anaconda._set_option("debug", True)

        # Set "nosave flags".
        if hasattr(opts, "save_input_kickstart"):
            self.anaconda._set_option("save_input_kickstart", opts.save_input_kickstart)
        if hasattr(opts, "save_output_kickstart"):
            self.anaconda._set_option("save_output_kickstart", opts.save_output_kickstart)
        if hasattr(opts, "save_logs"):
            self.anaconda._set_option("save_logs", opts.save_logs)

        # Set the bootloader type.
        if opts.extlinux:
            self.bootloader._set_option("type", BootloaderType.EXTLINUX.value)

        # Set the boot loader flags.
        self.bootloader._set_option("nonibft_iscsi_boot", opts.nonibftiscsiboot)

        # Set the storage flags.
        self.storage._set_option("dmraid", opts.dmraid)
        self.storage._set_option("ibft", opts.ibft)
        self.storage._set_option("gpt", opts.gpt)
        self.storage._set_option("multipath_friendly_names", opts.multipath_friendly_names)

        # Set up the rescue mode.
        if opts.rescue:
            self.storage._set_option("allow_imperfect_devices", True)

        # Set the security flags.
        self.security._set_option("selinux", opts.selinux)

        # Set the type of the installation system.
        if opts.liveinst:
            self.system._set_option("type", SystemType.LIVE_OS.value)
        elif opts.images or opts.dirinstall:
            self.system._set_option("type", SystemType.UNKNOWN.value)
        else:
            self.system._set_option("type", SystemType.BOOT_ISO.value)

        # Set the type of the installation target.
        if opts.images:
            # The image installation is requested.
            self.target._set_option("type", TargetType.IMAGE.value)
        elif opts.dirinstall:
            # The dir installation is requested.
            self.target._set_option("type", TargetType.DIRECTORY.value)
            self.target._set_option("physical_root", opts.dirinstall)

        # Set the payload flags.
        if opts.noverifyssl:
            self.payload._set_option("verify_ssl", not opts.noverifyssl)

        self.validate()


conf = AnacondaConfiguration.from_defaults()
