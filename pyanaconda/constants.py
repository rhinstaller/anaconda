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
# Author(s): Erik Troan <ewt@redhat.com>
#

from pyanaconda.i18n import N_

SELINUX_DEFAULT = 1

# where to look for 3rd party addons
ADDON_PATHS = ["/usr/share/anaconda/addons"]

# pull in kickstart constants as well
# pylint: disable-msg=W0401
from pykickstart.constants import *

# common string needs to be easy to change
from pyanaconda import product
productName = product.productName
productVersion = product.productVersion
productArch = product.productArch
bugzillaUrl = product.bugUrl
isFinal = product.isFinal

# for use in device names, eg: "fedora", "rhel"
shortProductName = productName.lower()
if productName.count(" "):
    shortProductName = ''.join(s[0] for s in shortProductName.split())

# DriverDisc Paths
DD_ALL = "/tmp/DD"
DD_FIRMWARE = "/tmp/DD/lib/firmware"
DD_RPMS = "/tmp/DD-*"

TRANSLATIONS_UPDATE_DIR="/tmp/updates/po"

ANACONDA_CLEANUP = "anaconda-cleanup"
ROOT_PATH = "/mnt/sysimage"
MOUNT_DIR = "/mnt/install"
DRACUT_REPODIR = "/run/install/repo"
DRACUT_ISODIR = "/run/install/source"
ISO_DIR = MOUNT_DIR + "/isodir"
IMAGE_DIR = MOUNT_DIR + "/image"
INSTALL_TREE = MOUNT_DIR + "/source"
BASE_REPO_NAME = "anaconda"

# NOTE: this should be LANG_TERRITORY.CODESET, e.g. en_US.UTF-8
DEFAULT_LANG = "en_US.UTF-8"

DEFAULT_VC_FONT = "latarcyrheb-sun16"

DEFAULT_KEYBOARD = "us"

DRACUT_SHUTDOWN_EJECT = "/run/initramfs/usr/lib/dracut/hooks/shutdown/99anaconda-eject.sh"

# VNC questions
USEVNC = N_("Start VNC")
USETEXT = N_("Use text mode")

# Runlevel files
RUNLEVELS = {3: 'multi-user.target', 5: 'graphical.target'}

# Network
NETWORK_CONNECTION_TIMEOUT = 45  # in seconds
NETWORK_CONNECTED_CHECK_INTERVAL = 0.1  # in seconds

# DBus
DEFAULT_DBUS_TIMEOUT = -1       # use default

# Thread names
THREAD_EXECUTE_STORAGE = "AnaExecuteStorageThread"
THREAD_STORAGE = "AnaStorageThread"
THREAD_STORAGE_WATCHER = "AnaStorageWatcher"
THREAD_CHECK_STORAGE = "AnaCheckStorageThread"
THREAD_CUSTOM_STORAGE_INIT = "AnaCustomStorageInit"
THREAD_WAIT_FOR_CONNECTING_NM = "AnaWaitForConnectingNMThread"
THREAD_PAYLOAD = "AnaPayloadThread"
THREAD_PAYLOAD_MD = "AnaPayloadMDThread"
THREAD_INPUT_BASENAME = "AnaInputThread"
THREAD_SYNC_TIME_BASENAME = "AnaSyncTime"
THREAD_EXCEPTION_HANDLING_TEST = "AnaExceptionHandlingTest"
THREAD_LIVE_PROGRESS = "AnaLiveProgressThread"
THREAD_SOFTWARE_WATCHER = "AnaSoftwareWatcher"
THREAD_CHECK_SOFTWARE = "AnaCheckSoftwareThread"
THREAD_SOURCE_WATCHER = "AnaSourceWatcher"
THREAD_INSTALL = "AnaInstallThread"
THREAD_CONFIGURATION = "AnaConfigurationThread"
THREAD_FCOE = "AnaFCOEThread"
THREAD_ISCSI_DISCOVER = "AnaIscsiDiscoverThread"
THREAD_ISCSI_LOGIN = "AnaIscsiLoginThread"
THREAD_GEOLOCATION_REFRESH = "AnaGeolocationRefreshThread"
THREAD_DATE_TIME = "AnaDateTimeThread"
THREAD_TIME_INIT = "AnaTimeInitThread"
THREAD_XKL_WRAPPER_INIT = "AnaXklWrapperInitThread"

# Geolocation constants

# geolocation providers
# - values are used by the geoloc CLI/boot option
GEOLOC_PROVIDER_FEDORA_GEOIP = "provider_fedora_geoip"
GEOLOC_PROVIDER_HOSTIP = "provider_hostip"
GEOLOC_PROVIDER_GOOGLE_WIFI = "provider_google_wifi"
# geocoding provider
GEOLOC_GEOCODER_NOMINATIM = "geocoder_nominatim"
# default providers
GEOLOC_DEFAULT_PROVIDER = GEOLOC_PROVIDER_FEDORA_GEOIP
GEOLOC_DEFAULT_GEOCODER = GEOLOC_GEOCODER_NOMINATIM
# timeout (in seconds)
GEOLOC_TIMEOUT = 3


ANACONDA_ENVIRON = "anaconda"
FIRSTBOOT_ENVIRON = "firstboot"

# Tainted hardware
UNSUPPORTED_HW = 1 << 28

# Password validation
PASSWORD_MIN_LEN = 6
PASSWORD_EMPTY_ERROR = N_("The password is empty.")
PASSWORD_CONFIRM_ERROR_GUI = N_("The passwords do not match.")
PASSWORD_CONFIRM_ERROR_TUI = N_("The passwords you entered were different.  Please try again.")
PASSWORD_WEAK = N_("The password you have provided is weak. You will have to press Done twice to confirm it.")
PASSWORD_WEAK_WITH_ERROR = N_("The password you have provided is weak: %s. You will have to press Done twice to confirm it.")
PASSWORD_WEAK_CONFIRM = N_("You have provided a weak password. Press Done again to use anyway.")
PASSWORD_WEAK_CONFIRM_WITH_ERROR = N_("You have provided a weak password: %s. Press Done again to use anyway.")

PASSWORD_STRENGTH_DESC = [N_("Empty"), N_("Weak"), N_("Fair"), N_("Good"), N_("Strong")]
