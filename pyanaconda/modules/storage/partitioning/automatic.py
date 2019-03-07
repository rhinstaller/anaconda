#
# Auto partitioning module.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import DEFAULT_AUTOPART_TYPE
from pyanaconda.dbus import DBus
from pyanaconda.core.signal import Signal
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.storage.constants import AutoPartitioningType
from pyanaconda.modules.storage.partitioning.base import PartitioningModule
from pyanaconda.modules.storage.partitioning.automatic_interface import AutoPartitioningInterface
from pyanaconda.modules.storage.partitioning.configure import StorageConfigureTask
from pyanaconda.modules.storage.partitioning.validate import StorageValidateTask
from pyanaconda.modules.storage.partitioning.automatic_execution import \
    AutomaticPartitioningExecutor

log = get_module_logger(__name__)


class AutoPartitioningModule(PartitioningModule):
    """The auto partitioning module."""

    def __init__(self):
        """Initialize the module."""
        super().__init__()
        self.enabled_changed = Signal()
        self._enabled = False

        self.type_changed = Signal()
        self._type = None

        self.fstype_changed = Signal()
        self._fstype = ""

        self.nohome_changed = Signal()
        self._nohome = False

        self.noboot_changed = Signal()
        self._noboot = False

        self.noswap_changed = Signal()
        self._noswap = False

        self.encrypted_changed = Signal()
        self._encrypted = False

        self.cipher_changed = Signal()
        self._cipher = ""

        self.passphrase_changed = Signal()
        self._passphrase = ""

        self.luks_version_changed = Signal()
        self._luks_version = ""

        self.pbkdf_changed = Signal()
        self._pbkdf = ""

        self.pbkdf_memory_changed = Signal()
        self._pbkdf_memory = 0

        self.pbkdf_time_changed = Signal()
        self._pbkdf_time = 0

        self.pbkdf_iterations_changed = Signal()
        self._pbkdf_iterations = 0

        self.escrowcert_changed = Signal()
        self._escrowcert = ""

        self.backup_passphrase_enabled_changed = Signal()
        self._backup_passphrase_enabled = ""

    def publish(self):
        """Publish the module."""
        DBus.publish_object(AUTO_PARTITIONING.object_path, AutoPartitioningInterface(self))

    def process_kickstart(self, data):
        """Process the kickstart data."""

        self.set_enabled(data.autopart.autopart)

        if data.autopart.type is not None:
            self.set_type(AutoPartitioningType(data.autopart.type))

        if data.autopart.fstype:
            self.set_fstype(data.autopart.fstype)

        self.set_nohome(data.autopart.nohome)
        self.set_noboot(data.autopart.noboot)
        self.set_noswap(data.autopart.noswap)

        if data.autopart.encrypted:
            self.set_encrypted(data.autopart.encrypted)
            self.set_passphrase(data.autopart.passphrase)
            self.set_luks_version(data.autopart.luks_version)
            self.set_pbkdf(data.autopart.pbkdf)
            self.set_pbkdf_memory(data.autopart.pbkdf_memory)
            self.set_pbkdf_time(data.autopart.pbkdf_time)
            self.set_pbkdf_iterations(data.autopart.pbkdf_iterations)
            self.set_escrowcert(data.autopart.escrowcert)
            self.set_backup_passphrase_enabled(data.autopart.backuppassphrase)
            self.set_cipher(data.autopart.cipher)

    def setup_kickstart(self, data):
        """Setup the kickstart data."""

        data.autopart.autopart = self.enabled
        data.autopart.fstype = self.fstype

        if not self.is_type_default:
            data.autopart.type = self.type.value

        data.autopart.nohome = self.nohome
        data.autopart.noboot = self.noboot
        data.autopart.noswap = self.noswap

        data.autopart.encrypted = self.encrypted
        data.autopart.passphrase = self.passphrase
        data.autopart.luks_version = self.luks_version
        data.autopart.pbkdf = self.pbkdf
        data.autopart.pbkdf_memory = self.pbkdf_memory
        data.autopart.pbkdf_time = self.pbkdf_time
        data.autopart.pbkdf_iterations = self.pbkdf_iterations
        data.autopart.escrowcert = self.escrowcert
        data.autopart.backuppassphrase = self.backup_passphrase_enabled
        data.autopart.cipher = self.cipher

    @property
    def enabled(self):
        """Is the auto partitioning enabled?"""
        return self._enabled

    def set_enabled(self, enabled):
        """Is the auto partitioning enabled?

        :param enabled: a boolean value
        """
        self._enabled = enabled
        self.enabled_changed.emit()
        log.debug("Enabled is set to '%s'.", enabled)

    @property
    def is_type_default(self):
        """Is the type of a filesystem set to a default value?"""
        return self._type is None

    @property
    def type(self):
        """Type of a filesystem used on the partitions."""
        if self.is_type_default:
            return AutoPartitioningType(DEFAULT_AUTOPART_TYPE)

        return self._type

    def set_type(self, scheme):
        """Set the partitioning scheme.

        :param scheme: an instance of AutoPartitioningType
        """
        self._type = scheme
        self.type_changed.emit()
        log.debug("Type is set to '%s'.", scheme)

    @property
    def fstype(self):
        """Type of a filesystem used on the partitions."""
        return self._fstype

    def set_fstype(self, fstype):
        """Set the type of a filesystem used on the partitions.

        :param fstype: a string with the filesystem type
        """
        self._fstype = fstype
        self.fstype_changed.emit()
        log.debug("Filesystem type is set to '%s'.", fstype)

    @property
    def nohome(self):
        """Do not create a /home partition."""
        return self._nohome

    def set_nohome(self, nohome):
        """Enable or disable creation of a /home partition.

        :param nohome: a boolean value
        """
        self._nohome = nohome
        self.nohome_changed.emit()
        log.debug("Nohome is set to '%s'.", nohome)

    @property
    def noboot(self):
        """Do not create a /boot partition."""
        return self._noboot

    def set_noboot(self, noboot):
        """Enable or disable creation of a /boot partition.

        :param noboot: a boolean value
        """
        self._noboot = noboot
        self.noboot_changed.emit()
        log.debug("Noboot is set to '%s'.", noboot)

    @property
    def noswap(self):
        """Do not create a swap partition."""
        return self._noswap

    def set_noswap(self, noswap):
        """Enable or disable creation of a swap partition.

        :param noswap: a boolean value
        """
        self._noswap = noswap
        self.noswap_changed.emit()
        log.debug("Noswap is set to '%s'.", noswap)

    @property
    def encrypted(self):
        """Should all devices with support be encrypted by default?"""
        return self._encrypted

    def set_encrypted(self, encrypted):
        """Set if all devices with support should be encrypted by default.

        :param encrypted: a boolean value
        """
        self._encrypted = encrypted
        self.encrypted_changed.emit()
        log.debug("Encrypted is set to '%s'.", encrypted)

    @property
    def cipher(self):
        """Encryption algorithm used to encrypt the filesystem."""
        return self._cipher

    def set_cipher(self, cipher):
        """Set the encryption algorithm used to encrypt the filesystem.

        :param cipher: a name of an algorithm
        """
        self._cipher = cipher
        self.cipher_changed.emit()
        log.debug("Cipher is set to '%s'.", cipher)

    @property
    def passphrase(self):
        """Default passphrase for all encrypted devices."""
        return self._passphrase

    def set_passphrase(self, passphrase):
        """Set a default passphrase for all encrypted devices.

        :param passphrase: a string with a passphrase
        """
        self._passphrase = passphrase
        self.passphrase_changed.emit()
        log.debug("Passphrase is set.")

    @property
    def luks_version(self):
        """Version of LUKS."""
        return self._luks_version

    def set_luks_version(self, version):
        """Set the version of LUKS.

        :param version: a string with the LUKS version
        """
        self._luks_version = version
        self.luks_version_changed.emit()
        log.debug("LUKS version is set to '%s'.", version)

    @property
    def pbkdf(self):
        """The PBKDF algorithm."""
        return self._pbkdf

    def set_pbkdf(self, pbkdf):
        """Set the PBKDF algorithm.

        Set Password-Based Key Derivation Function (PBKDF)
        algorithm for LUKS keyslot.

        :param pbkdf: a name of the algorithm
        """
        self._pbkdf = pbkdf
        self.pbkdf_changed.emit()
        log.debug("PBKDF is set to '%s'.", pbkdf)

    @property
    def pbkdf_memory(self):
        """The memory cost for PBKDF."""
        return self._pbkdf_memory

    def set_pbkdf_memory(self, memory):
        """Set the memory cost for PBKDF.

        :param memory: the memory cost in kilobytes
        """
        self._pbkdf_memory = memory
        self.pbkdf_memory_changed.emit()
        log.debug("PBKDF memory is set to '%s'.", memory)

    @property
    def pbkdf_time(self):
        """The time to spend with PBKDF processing."""
        return self._pbkdf_time

    def set_pbkdf_time(self, time_ms):
        """Set the time to spend with PBKDF processing.

        Sets the number of milliseconds to spend with PBKDF
        passphrase processing.

        :param time_ms: a number of milliseconds
        """
        self._pbkdf_time = time_ms
        self.pbkdf_time_changed.emit()
        log.debug("PBKDF time is set to '%s'.", time_ms)

    @property
    def pbkdf_iterations(self):
        """The number of iterations for PBKDF."""
        return self._pbkdf_iterations

    def set_pbkdf_iterations(self, iterations):
        """Set the number of iterations for PBKDF.

        Avoid PBKDF benchmark and set time cost (iterations) directly.

        :param iterations: a number of iterations
        """
        self._pbkdf_iterations = iterations
        self.pbkdf_iterations_changed.emit()
        log.debug("PBKDF iterations are set to '%s'.", iterations)

    @property
    def escrowcert(self):
        """URL of an X.509 certificate."""
        return self._escrowcert

    def set_escrowcert(self, url):
        """Set URL of an X.509 certificate.

        :param url: URL of an X.509 certificate
        """
        self._escrowcert = url
        self.escrowcert_changed.emit()
        log.debug("Escrowcert is set to '%s'.", url)

    @property
    def backup_passphrase_enabled(self):
        """Is the backup passphrase enabled?"""
        return self._backup_passphrase_enabled

    def set_backup_passphrase_enabled(self, enabled):
        """Enable or disable the backup passphrase.

        :param enabled: a boolean value
        """
        self._backup_passphrase_enabled = enabled
        self.backup_passphrase_enabled_changed.emit()
        log.debug("Backup passphrase enabled is set to '%s'.", enabled)

    def configure_with_task(self):
        """Schedule the partitioning actions."""
        task = StorageConfigureTask(self.storage, AutomaticPartitioningExecutor())
        path = self.publish_task(AUTO_PARTITIONING.namespace, task)
        return path

    def validate_with_task(self):
        """Validate the scheduled partitions."""
        task = StorageValidateTask(self.storage)
        path = self.publish_task(AUTO_PARTITIONING.namespace, task)
        return path
