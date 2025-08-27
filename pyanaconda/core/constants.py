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
import string
from enum import Enum

from pyanaconda.core.i18n import N_
from pyanaconda.core.product import get_product_name, get_product_version

# Use -1 to indicate that the selinux configuration is unset
SELINUX_DEFAULT = -1

# where to look for 3rd party addons
ADDON_PATHS = ["/usr/share/anaconda/addons"]

# The default virtio port.
VIRTIO_PORT = "/dev/virtio-ports/org.fedoraproject.anaconda.log.0"

# The clean-up tool.
ANACONDA_CLEANUP = "anaconda-cleanup"

# System mount points.
LIVE_MOUNT_POINT = "/run/initramfs/live"

# Source mount points.
MOUNT_DIR = "/run/install"
DRACUT_ISODIR = "/run/install/source"
DRACUT_REPO_DIR = "/run/install/repo"
ISO_DIR = MOUNT_DIR + "/isodir"
SOURCES_DIR = MOUNT_DIR + "/sources"

# Names of repositories.
BASE_REPO_NAME = "anaconda"

# Get list of repo names witch should be used as base repo
DEFAULT_REPOS = [
    get_product_name().split('-')[0].lower(),  # pylint: disable=no-member
    "fedora-modular-server",
    "rawhide",
    "BaseOS",      # Used by RHEL
    "baseos",      # Used by CentOS Stream
    "eln-baseos",  # Used by Fedora ELN
]

DBUS_ANACONDA_SESSION_ADDRESS = "DBUS_ANACONDA_SESSION_BUS_ADDRESS"

ANACONDA_BUS_CONF_FILE = "/usr/share/anaconda/dbus/anaconda-bus.conf"
ANACONDA_BUS_ADDR_FILE = "/run/anaconda/bus.address"

ANACONDA_CONFIG_DIR = "/etc/anaconda/"
ANACONDA_CONFIG_TMP = "/run/anaconda/anaconda.conf"

# file to store pid of the web viewer app to show Anaconda locally
WEBUI_VIEWER_PID_FILE = "/run/anaconda/webui_script.pid"
# flag file for Web UI to signalize that Anaconda backend is ready to be used
# FIXME: Web UI should monitor the initialization itself
BACKEND_READY_FLAG_FILE = "/run/anaconda/backend_ready"

# NOTE: this should be LANG_TERRITORY.CODESET, e.g. en_US.UTF-8
DEFAULT_LANG = "en_US.UTF-8"

DEFAULT_VC_FONT = "eurlatgr"

DEFAULT_KEYBOARD = "us"

DRACUT_SHUTDOWN_EJECT = "/run/initramfs/usr/lib/dracut/hooks/shutdown/99anaconda-eject.sh"

# RDP questions
USERDP = N_("Use graphical mode via Remote Desktop Protocol")
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

NETWORK_CAPABILITY_TEAM = 1

# Anaconda user agent
USER_AGENT = "%s (anaconda)/%s" % (get_product_name(), get_product_version())

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
THREAD_DATE_TIME = "AnaDateTimeThread"
THREAD_TIME_INIT = "AnaTimeInitThread"
THREAD_DASDFMT = "AnaDasdfmtThread"
THREAD_KEYBOARD_INIT = "AnaKeyboardThread"
THREAD_ADD_LAYOUTS_INIT = "AnaAddLayoutsInitThread"
THREAD_NTP_SERVER_CHECK = "AnaNTPserver"
THREAD_DBUS_TASK = "AnaTaskThread"
THREAD_SUBSCRIPTION = "AnaSubscriptionThread"
THREAD_SUBSCRIPTION_SPOKE_INIT = "AnaSubscriptionSpokeInitThread"
THREAD_RDP_OBTAIN_HOSTNAME = "AnaRDPObtainHostnameThread"

# Geolocation constants

# geolocation providers
# - values are used by the geoloc CLI/boot option
GEOLOC_PROVIDER_FEDORA_GEOIP = "provider_fedora_geoip"
GEOLOC_PROVIDER_HOSTIP = "provider_hostip"
# default provider
GEOLOC_DEFAULT_PROVIDER = GEOLOC_PROVIDER_FEDORA_GEOIP
# geolocation URLs - values used by config file
GEOLOC_URL_FEDORA_GEOIP = "https://geoip.fedoraproject.org/city"
GEOLOC_URL_HOSTIP = "https://api.hostip.info/get_json.php"
# timeout for the network connection used for geolocation (in seconds)
GEOLOC_CONNECTION_TIMEOUT = 5

ANACONDA_ENVIRON = "anaconda"
FIRSTBOOT_ENVIRON = "firstboot"

# Storage messages
WARNING_NO_DISKS_DETECTED = N_(
    "No disks detected.  Please shut down the computer, connect at least one disk, and restart "
    "to complete installation."
)

WARNING_NO_DISKS_SELECTED = N_(
    "No disks selected; please select at least one disk to install to."
)

RHEL_SMT_URL = "https://red.ht/rhel-smt"

# Kernel messages.
WARNING_SMT_ENABLED_GUI = N_(
    "Simultaneous Multithreading (SMT) technology can provide performance "
    "improvements for certain workloads, but introduces several publicly "
    "disclosed security issues. You have the option of disabling SMT, which "
    "may impact performance. If you choose to leave SMT enabled, please read "
    "%s to understand your potential risks and learn "
    "about other ways to mitigate these risks."
)

# This message is shorter to fit on the screen.
WARNING_SMT_ENABLED_TUI = N_(
    "Simultaneous Multithreading (SMT) may improve performance for certain "
    "workloads, but introduces several publicly disclosed security issues. "
    "You can disable SMT, which may impact performance. Please read "
    "%s to understand potential risks and learn about "
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
# TRANSLATORS: Password error message from libreport library needs to be joined with "You will have to press <b>Done</b> twice to confirm it." add a missing '.'
PASSWORD_ERROR_CONCATENATION = N_("{}. {}")


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

PACKAGES_LIST_FILE = "/root/lorax-packages.log"

CMDLINE_FILES = [
    "/proc/cmdline",
    "/run/install/cmdline",
    "/run/install/cmdline.d/*.conf",
    "/etc/cmdline"
]

# cmdline arguments that append instead of overwrite
CMDLINE_APPEND = ["modprobe.blacklist", "ifname", "ip"]
CMDLINE_LIST = ["addrepo"]

# An estimated ratio for metadata size to total disk space.
STORAGE_METADATA_RATIO = 0.1

# Constants for reporting status to IPMI.  These are from the IPMI spec v2 rev1.1, page 512.
IPMI_STARTED = 0x7          # installation started
IPMI_FINISHED = 0x8         # installation finished successfully
IPMI_ABORTED = 0x9          # installation finished unsuccessfully, due to some non-exn error
IPMI_FAILED = 0xA           # installation hit an exception

# Wayland socket name to use
WAYLAND_SOCKET_NAME = "wl-sysinstall-0"

# X display number to use
X_DISPLAY_NUMBER = 1

# Payload status messages
PAYLOAD_STATUS_PROBING_STORAGE = N_("Probing storage...")
PAYLOAD_STATUS_SETTING_SOURCE = N_("Setting up installation source...")
PAYLOAD_STATUS_INVALID_SOURCE = N_("Error setting up repositories")
PAYLOAD_STATUS_CHECKING_SOFTWARE = N_("Checking software dependencies...")

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
    DisplayModes.TUI: "text mode",
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
LOGGER_SIMPLELINE = "simpleline"

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
PAYLOAD_TYPE_FLATPAK = "FLATPAK"
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
SOURCE_TYPE_LIVE_TAR = "LIVE_TAR"
SOURCE_TYPE_RPM_OSTREE = "RPM_OSTREE"
SOURCE_TYPE_RPM_OSTREE_CONTAINER = "RPM_OSTREE_CONTAINER"
SOURCE_TYPE_FLATPAK = "FLATPAK"
SOURCE_TYPE_HMC = "HMC"
SOURCE_TYPE_CDROM = "CDROM"
SOURCE_TYPE_CLOSEST_MIRROR = "CLOSEST_MIRROR"
SOURCE_TYPE_REPO_FILES = "REPO_FILES"
SOURCE_TYPE_REPO_PATH = "REPO_PATH"
SOURCE_TYPE_NFS = "NFS"
SOURCE_TYPE_URL = "URL"
SOURCE_TYPE_HDD = "HDD"
SOURCE_TYPE_CDN = "CDN"

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

# Repository origin.
REPO_ORIGIN_SYSTEM = "SYSTEM"
REPO_ORIGIN_USER = "USER"
REPO_ORIGIN_TREEINFO = "TREEINFO"

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

# Timezone setting priorities
TIMEZONE_PRIORITY_DEFAULT = 0
TIMEZONE_PRIORITY_LANGUAGE = 30
TIMEZONE_PRIORITY_GEOLOCATION = 50
TIMEZONE_PRIORITY_KICKSTART = 70
TIMEZONE_PRIORITY_USER = 90

# FIPS mode minimum LUKS passphrase length
FIPS_PASSPHRASE_MIN_LENGTH = 8


# Installation categories
CATEGORY_UNDEFINED = "UNDEFINED"
CATEGORY_ENVIRONMENT = "ENVIRONMENT_CONFIGURATION"
CATEGORY_STORAGE = "STORAGE_CONFIGURATION"
CATEGORY_SOFTWARE = "SOFTWARE_INSTALLATION"
CATEGORY_BOOTLOADER = "BOOTLOADER_INSTALLATION"
CATEGORY_SYSTEM = "SYSTEM_CONFIGURATION"

# Installation phases
INSTALLATION_PHASE_PREINSTALL = "pre-install"
