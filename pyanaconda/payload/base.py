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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
from abc import ABCMeta, abstractmethod

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core import util
from pyanaconda.core.kernel import kernel_arguments
from pyanaconda.payload.requirement import PayloadRequirements
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

        # A list of verbose error strings from the subclass
        self.verbose_errors = []

        self._session = util.requests_session()

        # Additional packages required by installer based on used features
        self.requirements = PayloadRequirements()

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
        self.verbose_errors = []

    def unsetup(self):
        """Invalidate a previously setup payload."""
        pass

    def post_setup(self):
        """Run specific payload post-configuration tasks on the end of
        the restart_thread call.

        This method could be overriden.
        """
        pass

    def release(self):
        """Release any resources in use by this object, but do not do final
        cleanup.  This is useful for dealing with payload backends that do
        not get along well with multithreaded programs.
        """
        pass

    def reset(self):
        """Reset the instance, not including ksdata."""
        pass

    @property
    def needs_network(self):
        return False

    def is_language_supported(self, language):
        """Is the given language supported by the payload?

        :param language: a name of the language
        """
        return True

    def is_locale_supported(self, language, locale):
        """Is the given locale supported by the payload?

        :param language: a name of the language
        :param locale: a name of the locale
        """
        return True

    def language_groups(self):
        return []

    def langpacks(self):
        return []

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

    @property
    def needs_storage_configuration(self):
        """Should we write the storage before doing the installation?

        Some payloads require that the storage configuration will be written out
        before doing installation. Right now, this is basically just the dnfpayload.
        """
        return False

    @property
    def handles_bootloader_configuration(self):
        """Whether this payload backend writes the bootloader configuration itself; if
        False (the default), the generic bootloader configuration code will be used.
        """
        return False

    def recreate_initrds(self):
        """Recreate the initrds by calling new-kernel-pkg or dracut

        This needs to be done after all configuration files have been
        written, since dracut depends on some of them.

        :returns: None
        """
        if os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            use_dracut = False
        else:
            log.debug("new-kernel-pkg does not exist, using dracut instead.")
            use_dracut = True

        for kernel in self.kernel_version_list:
            log.info("recreating initrd for %s", kernel)
            if not conf.target.is_image:
                if use_dracut:
                    util.execInSysroot("depmod", ["-a", kernel])
                    util.execInSysroot("dracut",
                                       ["-f",
                                        "/boot/initramfs-%s.img" % kernel,
                                        kernel])
                else:
                    util.execInSysroot("new-kernel-pkg",
                                       ["--mkinitrd", "--dracut", "--depmod",
                                        "--update", kernel])

                # if the installation is running in fips mode then make sure
                # fips is also correctly enabled in the installed system
                if kernel_arguments.get("fips") == "1":
                    # We use the --no-bootcfg option as we don't want fips-mode-setup to
                    # modify the bootloader configuration.
                    # Anaconda already does everything needed & it would require grubby to
                    # be available on the system.
                    util.execInSysroot("fips-mode-setup", ["--enable", "--no-bootcfg"])

            else:
                # hostonly is not sensible for disk image installations
                # using /dev/disk/by-uuid/ is necessary due to disk image naming
                util.execInSysroot("dracut",
                                   ["-N",
                                    "--persistent-policy", "by-uuid",
                                    "-f", "/boot/initramfs-%s.img" % kernel,
                                    kernel])

    def post_install(self):
        """Perform post-installation tasks."""

        # write out static config (storage, modprobe, keyboard, ??)
        #   kickstart should handle this before we get here
        from pyanaconda.modules.payloads.base.initialization import CopyDriverDisksFilesTask
        CopyDriverDisksFilesTask(conf.target.system_root).run()

        log.info("Installation requirements: %s", self.requirements)
        if not self.requirements.applied:
            log.info("Some of the requirements were not applied.")
