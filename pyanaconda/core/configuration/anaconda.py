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
from pyanaconda.core.configuration.product import ProductLoader
from pyanaconda.core.configuration.ui import UserInterfaceSection
from pyanaconda.core.configuration.timezone import TimezoneSection
from pyanaconda.core.constants import ANACONDA_CONFIG_TMP, ANACONDA_CONFIG_DIR, \
    GEOLOC_PROVIDER_FEDORA_GEOIP, GEOLOC_PROVIDER_HOSTIP, GEOLOC_DEFAULT_PROVIDER, \
    GEOLOC_URL_FEDORA_GEOIP, GEOLOC_URL_HOSTIP

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
        self._timezone = TimezoneSection(
            "Timezone", self.get_parser()
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

    @property
    def timezone(self):
        """The Timezone section."""
        return self._timezone

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

    def set_from_product(self, requested_product="", requested_variant="",
                         buildstamp_product="", buildstamp_variant="",
                         default_product=""):
        """Set the configuration from the product configuration files.

        We will use configuration files of a product requested by the user
        if any. Otherwise, we will use a product specified by the .buildstamp
        file or a default product.

        The configuration files are loaded from /etc/anaconda/product.d.

        :param str requested_product: a name of the requested product
        :param str requested_variant: a name of the requested variant
        :param str buildstamp_product: a name of the product from .buildstamp
        :param str buildstamp_variant: a name of the variant from .buildstamp
        :param str default_product: a name of the default product
        """
        loader = ProductLoader()
        loader.load_products(os.path.join(ANACONDA_CONFIG_DIR, "product.d"))

        # Use the requested product name and variant name.
        if requested_product:

            if not loader.check_product(requested_product, requested_variant):
                raise ConfigurationError(
                    "Unable to find any suitable configuration files for "
                    "the product name '{}' and the variant name '{}'."
                    "".format(requested_product, requested_variant)
                )

            product_name = requested_product
            variant_name = requested_variant

        # Or use the product name and the variant name from .buildstamp.
        elif loader.check_product(buildstamp_product, buildstamp_variant):
            product_name = buildstamp_product
            variant_name = buildstamp_variant

        # Or the product name from .buildstamp.
        elif loader.check_product(buildstamp_product):
            product_name = buildstamp_product
            variant_name = ""

        # Or use the default product name.
        elif loader.check_product(default_product):
            product_name = default_product
            variant_name = ""

        # Or fail.
        else:
            raise ConfigurationError(
                "Unable to find any suitable configuration files for this product."
            )

        # Read the configuration files of the product.
        config_paths = loader.collect_configurations(product_name, variant_name)

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

        # Set geolocation provider
        # FIXME: This will be removed once the boot option becomes a boolean
        if "geoloc" in opts and opts.geoloc and opts.geoloc != "0":
            if isinstance(opts.geoloc, str) and opts.geoloc.startswith("provider"):
                log.warning("Setting the geolocation provider from the inst.geoloc boot option "
                            "is deprecated and will be removed in the future. Use the "
                            "geolocation_provider=<URL> option in the configuration files.")
            self.timezone._set_option(
                "geolocation_provider",
                _convert_geoloc_provider_id_to_url(opts.geoloc)
            )

        self.validate()


def _convert_geoloc_provider_id_to_url(provider_id):
    """Convert provider ID to URL of the corresponding service.

    :param str provider_id: id of the geolocation provider service
    :return str: URL to use
    """
    available_providers = {
        GEOLOC_PROVIDER_FEDORA_GEOIP: GEOLOC_URL_FEDORA_GEOIP,
        GEOLOC_PROVIDER_HOSTIP: GEOLOC_URL_HOSTIP,
    }
    try:
        return available_providers[provider_id]
    except KeyError:
        log.error('Conf: Geoloc: wrong provider id specified: %s, using default %s',
                  provider_id, GEOLOC_DEFAULT_PROVIDER)
        return available_providers[GEOLOC_DEFAULT_PROVIDER]


conf = AnacondaConfiguration.from_defaults()
