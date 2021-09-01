#
# constants.py: anaconda constants
#
# Copyright (C) 2001  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# Used for digits, ascii_letters, punctuation constants
import string # pylint: disable=deprecated-module
from pyanaconda.core.i18n import N_

from enum import Enum

# Use -1 to indicate that the selinux configuration is unset
SELINUX_DEFAULT = -1

# where to look for 3rd party addons
ADDON_PATHS = ["/usr/share/anaconda/addons"]

# common string needs to be easy to change
from pyanaconda import product
productName = product.productName
productVersion = product.productVersion
isFinal = product.isFinal
shortProductName = product.shortProductName

# The default virtio port.
VIRTIO_PORT = "/dev/virtio-ports/org.fedoraproject.anaconda.log.0"

ANACONDA_CLEANUP = "anaconda-cleanup"
MOUNT_DIR = "/run/install"
DRACUT_ISODIR = "/run/install/source"
ISO_DIR = MOUNT_DIR + "/isodir"
IMAGE_DIR = MOUNT_DIR + "/image"
INSTALL_TREE = MOUNT_DIR + "/source"
SOURCES_DIR = MOUNT_DIR + "/sources"
BASE_REPO_NAME = "anaconda"

# Get list of repo names witch should be used as base repo
DEFAULT_REPOS = [productName.split('-')[0].lower(),  # pylint: disable=no-member
                 "fedora-modular-server",
                 "rawhide",
                 "BaseOS",  # Used by RHEL
                 "baseos"]  # Used by CentOS Stream

DBUS_ANACONDA_SESSION_ADDRESS = "DBUS_ANACONDA_SESSION_BUS_ADDRESS"

ANACONDA_BUS_CONF_FILE = "/usr/share/anaconda/dbus/anaconda-bus.conf"
ANACONDA_BUS_ADDR_FILE = "/run/anaconda/bus.address"

ANACONDA_DATA_DIR = "/usr/share/anaconda"
ANACONDA_CONFIG_DIR = "/etc/anaconda/"
ANACONDA_CONFIG_TMP = "/run/anaconda/anaconda.conf"

# NOTE: this should be LANG_TERRITORY.CODESET, e.g. en_US.UTF-8
DEFAULT_LANG = "en_US.UTF-8"

DEFAULT_VC_FONT = "eurlatgr"

DEFAULT_KEYBOARD = "us"

DRACUT_SHUTDOWN_EJECT = "/run/initramfs/usr/lib/dracut/hooks/shutdown/99anaconda-eject.sh"

# Help.
HELP_MAIN_PAGE_GUI = "Installation_Guide.xml"
HELP_MAIN_PAGE_TUI = "Installation_Guide.txt"

# VNC questions
USEVNC = N_("Start VNC")
USETEXT = N_("Use text mode")

# Quit message
QUIT_MESSAGE = N_("Do you really want to quit?")

# Runlevel files
TEXT_ONLY_TARGET = 'multi-user.target'
GRAPHICAL_TARGET = 'graphical.target'

# Network

# Requests package (where this constant is used) recommends to have timeout slightly
# above multiple of 3 because of it is default packet re-transmission window.
# See: https://3.python-requests.org/user/advanced/#timeouts
NETWORK_CONNECTION_TIMEOUT = 46  # in seconds
NETWORK_CONNECTED_CHECK_INTERVAL = 0.1  # in seconds

# DBus
DEFAULT_DBUS_TIMEOUT = -1       # use default

# Thread names
THREAD_EXECUTE_STORAGE = "AnaExecuteStorageThread"
THREAD_STORAGE = "AnaStorageThread"
THREAD_STORAGE_WATCHER = "AnaStorageWatcher"
THREAD_WAIT_FOR_CONNECTING_NM = "AnaWaitForConnectingNMThread"
THREAD_PAYLOAD = "AnaPayloadThread"
THREAD_PAYLOAD_RESTART = "AnaPayloadRestartThread"
THREAD_EXCEPTION_HANDLING_TEST = "AnaExceptionHandlingTest"
THREAD_LIVE_PROGRESS = "AnaLiveProgressThread"
THREAD_SOFTWARE_WATCHER = "AnaSoftwareWatcher"
THREAD_CHECK_SOFTWARE = "AnaCheckSoftwareThread"
THREAD_SOURCE_WATCHER = "AnaSourceWatcher"
THREAD_INSTALL = "AnaInstallThread"
THREAD_GEOLOCATION_REFRESH = "AnaGeolocationRefreshThread"
THREAD_DATE_TIME = "AnaDateTimeThread"
THREAD_TIME_INIT = "AnaTimeInitThread"
THREAD_DASDFMT = "AnaDasdfmtThread"
THREAD_KEYBOARD_INIT = "AnaKeyboardThread"
THREAD_ADD_LAYOUTS_INIT = "AnaAddLayoutsInitThread"
THREAD_NTP_SERVER_CHECK = "AnaNTPserver"
THREAD_DBUS_TASK = "AnaTaskThread"
THREAD_SUBSCRIPTION = "AnaSubscriptionThread"
THREAD_SUBSCRIPTION_SPOKE_INIT = "AnaSubscriptionSpokeInitThread"

# Geolocation constants

# geolocation providers
# - values are used by the geoloc CLI/boot option
GEOLOC_PROVIDER_FEDORA_GEOIP = "provider_fedora_geoip"
GEOLOC_PROVIDER_HOSTIP = "provider_hostip"
# default provider
GEOLOC_DEFAULT_PROVIDER = GEOLOC_PROVIDER_FEDORA_GEOIP
# how long should the GUI wait for the geolocation thread to finish (in seconds)
# - GUI starts this count once it finishes its initialization
# - the geoloc thread is started early and in most cases will be already done
#   when GUI finishes its initialization, so no delays will be introduced
GEOLOC_TIMEOUT = 3
# timeout for the network connection used for geolocation (in seconds)
GEOLOC_CONNECTION_TIMEOUT = 5

ANACONDA_ENVIRON = "anaconda"
FIRSTBOOT_ENVIRON = "firstboot"

# Tainted hardware
TAINT_SUPPORT_REMOVED = 27
TAINT_HARDWARE_UNSUPPORTED = 28

WARNING_SUPPORT_REMOVED = N_(
    "Support for this hardware has been removed in this major OS release. Please check the "
    "removed functionality section of the release notes."
)

WARNING_HARDWARE_UNSUPPORTED = N_(
    "This hardware (or a combination thereof) is not supported by Red Hat. For more information "
    "on supported hardware, please refer to http://www.redhat.com/hardware."
)

# Storage messages
WARNING_NO_DISKS_DETECTED = N_(
    "No disks detected.  Please shut down the computer, connect at least one disk, and restart "
    "to complete installation."
)

WARNING_NO_DISKS_SELECTED = N_(
    "No disks selected; please select at least one disk to install to."
)

# Kernel messages.
WARNING_SMT_ENABLED_GUI = N_(
    "Simultaneous Multithreading (SMT) technology can provide performance "
    "improvements for certain workloads, but introduces several publicly "
    "disclosed security issues. You have the option of disabling SMT, which "
    "may impact performance. If you choose to leave SMT enabled, please read "
    "https://red.ht/rhel-smt to understand your potential risks and learn "
    "about other ways to mitigate these risks."
)

# This message is shorter to fit on the screen.
WARNING_SMT_ENABLED_TUI = N_(
    "Simultaneous Multithreading (SMT) may improve performance for certain "
    "workloads, but introduces several publicly disclosed security issues. "
    "You can disable SMT, which may impact performance. Please read "
    "https://red.ht/rhel-smt to understand potential risks and learn about "
    "ways to mitigate these risks."
)


# Password type
class SecretType(Enum):
    PASSWORD = "password"
    PASSPHRASE = "passphrase"


# Password validation
SECRET_EMPTY_ERROR = {
    SecretType.PASSWORD : N_("The password is empty."),
    SecretType.PASSPHRASE : N_("The passphrase is empty.")
}
SECRET_CONFIRM_ERROR_GUI = {
    SecretType.PASSWORD : N_("The passwords do not match."),
    SecretType.PASSPHRASE : N_("The passphrases do not match.")
}
SECRET_CONFIRM_ERROR_TUI = {
    SecretType.PASSWORD : N_("The passwords you entered were different. Please try again."),
    SecretType.PASSPHRASE : N_("The passphrases you entered were different. Please try again.")
}

# The secret-too-short constants is used to replace a libpwquality error message,
# which is why it does not end with a ".", like all the other do.
SECRET_TOO_SHORT = {
    SecretType.PASSWORD : N_("The password is too short"),
    SecretType.PASSPHRASE : N_("The passphrase is too short")
}
SECRET_WEAK = {
    SecretType.PASSWORD : N_("The password you have provided is weak."),
    SecretType.PASSPHRASE : N_("The passphrase you have provided is weak.")
}
SECRET_WEAK_WITH_ERROR = {
    SecretType.PASSWORD : N_("The password you have provided is weak:"),
    SecretType.PASSPHRASE : N_("The passphrase you have provided is weak:")
}
PASSWORD_FINAL_CONFIRM = N_("Press <b>Done</b> again to use the password anyway.")
SECRET_ASCII = {
    SecretType.PASSWORD : N_("The password you have provided contains non-ASCII characters. You may not be able to switch between keyboard layouts when typing it."),
    SecretType.PASSPHRASE : N_("The passphrase you have provided contains non-ASCII characters. You may not be able to switch between keyboard layouts when typing it.")
}
PASSWORD_DONE_TWICE = N_("You will have to press <b>Done</b> twice to confirm it.")
PASSWORD_SET = N_("Password set.")


class SecretStatus(Enum):
    EMPTY = N_("Empty")
    TOO_SHORT = N_("Too short")
    WEAK = N_("Weak")
    FAIR = N_("Fair")
    GOOD = N_("Good")
    STRONG = N_("Strong")


PASSWORD_HIDE = N_("Hide password.")
PASSWORD_SHOW = N_("Show password.")

PASSWORD_HIDE_ICON = "anaconda-password-show-off"
PASSWORD_SHOW_ICON = "anaconda-password-show-on"

# The default types of password policies.
PASSWORD_POLICY_ROOT = "root"
PASSWORD_POLICY_USER = "user"
PASSWORD_POLICY_LUKS = "luks"

# the number of seconds we consider a noticeable freeze of the UI
NOTICEABLE_FREEZE = 0.1

# all ASCII characters
PW_ASCII_CHARS = string.digits + string.ascii_letters + string.punctuation + " "

# Recognizing a tarfile
TAR_SUFFIX = (".tar", ".tbz", ".tgz", ".txz", ".tar.bz2", "tar.gz", "tar.xz")

# screenshots
SCREENSHOTS_DIRECTORY = "/tmp/anaconda-screenshots"

CMDLINE_FILES = [
    "/proc/cmdline",
    "/run/install/cmdline",
    "/run/install/cmdline.d/*.conf",
    "/etc/cmdline"
]

# cmdline arguments that append instead of overwrite
CMDLINE_APPEND = ["modprobe.blacklist", "ifname", "ip"]
CMDLINE_LIST = ["addrepo"]

# Default to these units when reading user input when no units given
SIZE_UNITS_DEFAULT = "MiB"

# An estimated ratio for metadata size to total disk space.
STORAGE_METADATA_RATIO = 0.1

# Constants for reporting status to IPMI.  These are from the IPMI spec v2 rev1.1, page 512.
IPMI_STARTED = 0x7          # installation started
IPMI_FINISHED = 0x8         # installation finished successfully
IPMI_ABORTED = 0x9          # installation finished unsuccessfully, due to some non-exn error
IPMI_FAILED = 0xA           # installation hit an exception

# X display number to use
X_DISPLAY_NUMBER = 1

# Payload status messages
PAYLOAD_STATUS_PROBING_STORAGE = N_("Probing storage...")
PAYLOAD_STATUS_PACKAGE_MD = N_("Downloading package metadata...")
PAYLOAD_STATUS_GROUP_MD = N_("Downloading group metadata...")

# Window title text
WINDOW_TITLE_TEXT = N_("Anaconda Installer")

# Types of time sources.
TIME_SOURCE_SERVER = "SERVER"
TIME_SOURCE_POOL = "POOL"

# NTP server checking
NTP_SERVER_OK = 0
NTP_SERVER_NOK = 1
NTP_SERVER_QUERY = 2

# Timeout for the NTP server check
NTP_SERVER_TIMEOUT = 5

# Storage checker constraints
STORAGE_MIN_RAM = "min_ram"
STORAGE_ROOT_DEVICE_TYPES = "root_device_types"
STORAGE_MIN_PARTITION_SIZES = "min_partition_sizes"
STORAGE_REQ_PARTITION_SIZES = "req_partition_sizes"
STORAGE_MUST_BE_ON_LINUXFS = "must_be_on_linuxfs"
STORAGE_MUST_BE_ON_ROOT = "must_be_on_root"
STORAGE_MUST_NOT_BE_ON_ROOT = "must_not_be_on_root"
STORAGE_REFORMAT_ALLOWLIST = "reformat_allowlist"
STORAGE_REFORMAT_BLOCKLIST = "reformat_blocklist"
STORAGE_SWAP_IS_RECOMMENDED = "swap_is_recommended"
STORAGE_LUKS2_MIN_RAM = "luks2_min_ram"


# Display modes
class DisplayModes(Enum):
    GUI = "GUI"
    TUI = "TUI"


DISPLAY_MODE_NAME = {
    DisplayModes.GUI: "graphical mode",
    DisplayModes.TUI: "text mode"
}

INTERACTIVE_MODE_NAME = {
    True: "interactive",
    False: "noninteractive"
}

# Loggers
LOGGER_ANACONDA_ROOT = "anaconda"
LOGGER_MAIN = "anaconda.main"
LOGGER_STDOUT = "anaconda.stdout"
LOGGER_PROGRAM = "program"
LOGGER_PACKAGING = "packaging"
LOGGER_DNF = "dnf"
LOGGER_LIBREPO = "librepo"  # second DNF logger for librepo
LOGGER_SIMPLELINE = "simpleline"
LOGGER_SENSITIVE_INFO = "sensitive_info"

# Timeout for starting X
X_TIMEOUT = 60

# Setup on boot actions.
SETUP_ON_BOOT_DEFAULT = -1
SETUP_ON_BOOT_DISABLED = 0
SETUP_ON_BOOT_ENABLED = 1
SETUP_ON_BOOT_RECONFIG = 2

# Clear partitions modes.
CLEAR_PARTITIONS_DEFAULT = -1
CLEAR_PARTITIONS_NONE = 0
CLEAR_PARTITIONS_ALL = 1
CLEAR_PARTITIONS_LIST = 2
CLEAR_PARTITIONS_LINUX = 3

# Bootloader modes.
BOOTLOADER_DISABLED = 0
BOOTLOADER_ENABLED = 1
BOOTLOADER_SKIPPED = 2

# Bootloader locations.
BOOTLOADER_LOCATION_DEFAULT = "DEFAULT"
BOOTLOADER_LOCATION_PARTITION = "PARTITION"
BOOTLOADER_LOCATION_MBR = "MBR"

# Bootloader timeout.
BOOTLOADER_TIMEOUT_UNSET = -1

# Bootloader drive.
BOOTLOADER_DRIVE_UNSET = ""

# Firewall mode.
FIREWALL_DEFAULT = -1
FIREWALL_DISABLED = 0
FIREWALL_ENABLED = 1
FIREWALL_USE_SYSTEM_DEFAULTS = 2

# Iscsi interface mode.
ISCSI_INTERFACE_UNSET = "none"
ISCSI_INTERFACE_DEFAULT = "default"
ISCSI_INTERFACE_IFACENAME = "bind"

# Partitioning methods.
PARTITIONING_METHOD_AUTOMATIC = "AUTOMATIC"
PARTITIONING_METHOD_CUSTOM = "CUSTOM"
PARTITIONING_METHOD_MANUAL = "MANUAL"
PARTITIONING_METHOD_INTERACTIVE = "INTERACTIVE"
PARTITIONING_METHOD_BLIVET = "BLIVET"

# Types of secret data.
SECRET_TYPE_NONE = "NONE"
SECRET_TYPE_HIDDEN = "HIDDEN"
SECRET_TYPE_TEXT = "TEXT"

# Types of requirements.
REQUIREMENT_TYPE_PACKAGE = "package"
REQUIREMENT_TYPE_GROUP = "group"

# Types of the payload.
PAYLOAD_TYPE_DNF = "DNF"
PAYLOAD_TYPE_LIVE_OS = "LIVE_OS"
PAYLOAD_TYPE_LIVE_IMAGE = "LIVE_IMAGE"
PAYLOAD_TYPE_RPM_OSTREE = "RPM_OSTREE"

# All live types of the payload.
PAYLOAD_LIVE_TYPES = (
    PAYLOAD_TYPE_LIVE_OS,
    PAYLOAD_TYPE_LIVE_IMAGE
)

# Types of the payload source.
SOURCE_TYPE_LIVE_OS_IMAGE = "LIVE_OS_IMAGE"
SOURCE_TYPE_LIVE_IMAGE = "LIVE_IMAGE"
SOURCE_TYPE_RPM_OSTREE = "RPM_OSTREE"
SOURCE_TYPE_FLATPAK = "FLATPAK"
SOURCE_TYPE_HMC = "HMC"
SOURCE_TYPE_CDROM = "CDROM"
SOURCE_TYPE_CLOSEST_MIRROR = "CLOSEST_MIRROR"
SOURCE_TYPE_REPO_FILES = "REPO_FILES"
SOURCE_TYPE_NFS = "NFS"
SOURCE_TYPE_URL = "URL"
SOURCE_TYPE_HDD = "HDD"
SOURCE_TYPE_CDN = "CDN"

# All types that use repo files.
SOURCE_REPO_FILE_TYPES = (
    SOURCE_TYPE_REPO_FILES,
    SOURCE_TYPE_CLOSEST_MIRROR,
    SOURCE_TYPE_CDN,
)

# Payload sources overriden by the CDN

# This set lists sources the Red Hat CDN should automatically
# override if the system gets registered during installation.
# At the moment there is just the CDROM source, as almost
# always the CDN content will be much more up to date and
# more secure than the local content on the DVD image.
SOURCE_TYPES_OVERRIDEN_BY_CDN = (
    SOURCE_TYPE_CDROM
)

# Payload URL source types.
URL_TYPE_BASEURL = "BASEURL"
URL_TYPE_MIRRORLIST = "MIRRORLIST"
URL_TYPE_METALINK = "METALINK"

URL_TYPES = (
    URL_TYPE_BASEURL,
    URL_TYPE_MIRRORLIST,
    URL_TYPE_METALINK
)

# Default values of DNF configuration.
DNF_DEFAULT_REPO_COST = 1000
DNF_DEFAULT_TIMEOUT = -1
DNF_DEFAULT_RETRIES = -1

# Group package types.
GROUP_PACKAGE_TYPE_MANDATORY = "mandatory"
GROUP_PACKAGE_TYPE_CONDITIONAL = "conditional"
GROUP_PACKAGE_TYPE_DEFAULT = "default"
GROUP_PACKAGE_TYPE_OPTIONAL = "optional"

GROUP_PACKAGE_TYPES_ALL = [
    GROUP_PACKAGE_TYPE_MANDATORY,
    GROUP_PACKAGE_TYPE_DEFAULT,
    GROUP_PACKAGE_TYPE_CONDITIONAL,
    GROUP_PACKAGE_TYPE_OPTIONAL,
]

GROUP_PACKAGE_TYPES_REQUIRED = [
    GROUP_PACKAGE_TYPE_MANDATORY,
    GROUP_PACKAGE_TYPE_CONDITIONAL,
]

# The multilib policy.
MULTILIB_POLICY_ALL = "all"
MULTILIB_POLICY_BEST = "best"

# Languages marked for installation via RPM macros.
RPM_LANGUAGES_NONE = "none"  # represents %{nil}
RPM_LANGUAGES_ALL = "all"

# Subscription request types
#
# Subscription request can currently be one of two types:
# - using username and password for authentication
# - using organization id and one or more authentication keys
#   for authentication
SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD = "username_password"
SUBSCRIPTION_REQUEST_TYPE_ORG_KEY = "org_activation_key"

# Default authentication for subscription requests is
# username password - this is basically to avoid the invalid
# case of request not having a type set.
DEFAULT_SUBSCRIPTION_REQUEST_TYPE = SUBSCRIPTION_REQUEST_TYPE_USERNAME_PASSWORD

# How long to wait for the RHSM service to become available after it is started.
# - in seconds
# - based on the default 90 second systemd service activation timeout
RHSM_SERVICE_TIMEOUT = 90.0

# Path to the System Purpose configuration file on a system.
RHSM_SYSPURPOSE_FILE_PATH = "/etc/rhsm/syspurpose/syspurpose.json"

# GID and UID modes
ID_MODE_USE_VALUE = "ID_MODE_USE_VALUE"
ID_MODE_USE_DEFAULT = "ID_MODE_USE_DEFAULT"

# Path to the initrd critical warnings log file created by us in Dracut.
DRACUT_ERRORS_PATH = "/run/anaconda/initrd_errors.txt"
