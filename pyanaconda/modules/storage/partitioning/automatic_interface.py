#
# DBus interface for the auto partitioning module.
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
from pyanaconda.dbus.interface import dbus_interface
from pyanaconda.dbus.property import emits_properties_changed
from pyanaconda.dbus.typing import *  # pylint: disable=wildcard-import
from pyanaconda.modules.common.base import KickstartModuleInterfaceTemplate
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.storage.constants import AutoPartitioningType


@dbus_interface(AUTO_PARTITIONING.interface_name)
class AutoPartitioningInterface(KickstartModuleInterfaceTemplate):
    """DBus interface for the auto partitioning module."""

    def connect_signals(self):
        """Connect the signals."""
        super().connect_signals()

        self.watch_property("Enabled", self.implementation.enabled_changed)
        self.watch_property("Type", self.implementation.type_changed)
        self.watch_property("FilesystemType", self.implementation.fstype_changed)
        self.watch_property("NoHome", self.implementation.nohome_changed)
        self.watch_property("NoBoot", self.implementation.noboot_changed)
        self.watch_property("NoSwap", self.implementation.noswap_changed)
        self.watch_property("Encrypted", self.implementation.encrypted_changed)
        self.watch_property("Cipher", self.implementation.cipher_changed)
        self.watch_property("Passphrase", self.implementation.passphrase_changed)
        self.watch_property("Escrowcert", self.implementation.escrowcert_changed)

        self.watch_property(
            "BackupPassphraseEnabled", self.implementation.backup_passphrase_enabled_changed
        )

    @property
    def Enabled(self) -> Bool:
        """Is the auto partitioning enabled?"""
        return self.implementation.enabled

    @emits_properties_changed
    def SetEnabled(self, enabled: Bool):
        """Is the auto partitioning enabled?

        :param enabled: True if the autopartitioning is enabled, otherwise False
        """
        self.implementation.set_enabled(enabled)

    @property
    def Type(self) -> Int:
        """The partitioning scheme."""
        return self.implementation.type.value

    @emits_properties_changed
    def SetType(self, scheme: Int):
        """Set the partitioning scheme.

        Allowed values:
            -1 Use the default scheme.
            0  Create regular partitions.
            1  Use the btrfs scheme.
            2  Use the lvm scheme.
            3  Use the lvm thinp scheme.

        :param scheme: an id of the partitioning scheme
        """
        self.implementation.set_type(AutoPartitioningType(scheme))

    @property
    def FilesystemType(self) -> Str:
        """Type of a filesystem used on the partitions."""
        return self.implementation.fstype

    @emits_properties_changed
    def SetFilesystemType(self, fstype: Str):
        """Set the type of a filesystem used on the partitions.

        For example: ext4

        :param fstype: a name of a filesystem type
        """
        self.implementation.set_fstype(fstype)

    @property
    def NoHome(self) -> Bool:
        """Do not create a /home partition."""
        return self.implementation.nohome

    @property
    def NoBoot(self) -> Bool:
        """Do not create a /boot partition."""
        return self.implementation.noboot

    @property
    def NoSwap(self) -> Bool:
        """Do not create a swap partition."""
        return self.implementation.noswap

    @property
    def Encrypted(self) -> Bool:
        """Should all devices with support be encrypted by default?"""
        return self.implementation.encrypted

    @emits_properties_changed
    def SetEncrypted(self, encrypted: Bool):
        """Set if all devices with support should be encrypted by default.

        :param encrypted: True if should be encrypted, otherwise False
        """
        self.implementation.set_encrypted(encrypted)

    @property
    def Cipher(self) -> Str:
        """Encryption algorithm used to encrypt the filesystem."""
        return self.implementation.cipher

    @emits_properties_changed
    def SetCipher(self, cipher: Str):
        """Set the encryption algorithm used to encrypt the filesystem.

        For example: aes-xts-plain64

        :param cipher: a name of an algorithm
        """
        self.implementation.set_cipher(cipher)

    @property
    def Passphrase(self) -> Str:
        """Default passphrase for all encrypted devices.

        This is just a temporary property, because we shouldn't
        provide sensitive data.

        TODO: Remove this property once the module is completed.
        """
        return self.implementation.passphrase

    @emits_properties_changed
    def SetPassphrase(self, passphrase: Str):
        """Set a default passphrase for all encrypted devices.

        :param passphrase: a string with a passphrase
        """
        self.implementation.set_passphrase(passphrase)

    @property
    def Escrowcert(self) -> Str:
        """URL of an X.509 certificate."""
        return self.implementation.escrowcert

    @emits_properties_changed
    def SetEscrowcert(self, url: Str):
        """Set URL of an X.509 certificate.

        Store the data encryption keys of all encrypted volumes created during
        installation, encrypted using the certificate, as files in /root.

        :param url: URL of an X.509 certificate
        """
        self.implementation.set_escrowcert(url)

    @property
    def BackupPassphraseEnabled(self) -> Bool:
        """Is the backup passphrase enabled?"""
        return self.implementation.backup_passphrase_enabled

    @emits_properties_changed
    def SetBackupPassphraseEnabled(self, enabled: Bool):
        """Enable or disable the backup passphrase.

        In addition to storing the data encryption keys, generate a backup passphrase
        and add it to all encrypted volumes created during installation. Then store the
        passphrase, encrypted using the specified certificate as files in /root.

        :param enabled: True if the backup passphrase is enabled, otherwise False
        """
        self.implementation.set_backup_passphrase_enabled(enabled)
