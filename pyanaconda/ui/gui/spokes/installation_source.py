# Installation source spoke classes
#
# Copyright (C) 2019 Red Hat, Inc.
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
import re
import time

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF, SOURCE_TYPE_HDD, SOURCE_TYPE_URL, \
    SOURCE_TYPE_CDROM, SOURCE_TYPE_NFS, SOURCE_TYPE_HMC, URL_TYPE_BASEURL, \
    SOURCE_TYPE_CLOSEST_MIRROR, SOURCE_TYPE_CDN, PAYLOAD_STATUS_SETTING_SOURCE, \
    PAYLOAD_STATUS_INVALID_SOURCE, PAYLOAD_STATUS_CHECKING_SOFTWARE, SOURCE_TYPE_REPO_PATH, \
    DRACUT_REPO_DIR
from pyanaconda.core.i18n import _, CN_
from pyanaconda.core.path import join_paths
from pyanaconda.core.payload import parse_nfs_url, create_nfs_url, parse_hdd_url
from pyanaconda.core.regexes import URL_PARSE, HOSTNAME_PATTERN_WITHOUT_ANCHORS
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import NETWORK, STORAGE
from pyanaconda.modules.common.constants.services import SUBSCRIPTION
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.modules.common.structures.storage import DeviceFormatData
from pyanaconda.modules.common.util import is_module_available
from pyanaconda.modules.payloads.source.utils import verify_valid_repository
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.image import find_optical_install_media
from pyanaconda.payload.manager import payloadMgr
from pyanaconda.core.threads import thread_manager
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.context import context
from pyanaconda.ui.gui.helpers import GUISpokeInputCheckHandler
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.additional_repositories import AdditionalRepositoriesSection
from pyanaconda.ui.gui.spokes.lib.installation_source_helpers import ProxyDialog, \
    MediaCheckDialog, IsoChooser, PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP, PROTOCOL_NFS, \
    PROTOCOL_MIRROR, CLICK_FOR_DETAILS
from pyanaconda.ui.gui.utils import blockedHandler, fire_gtk_action
from pyanaconda.ui.gui.utils import gtk_call_once, really_hide, really_show
from pyanaconda.ui.helpers import InputCheck, SourceSwitchHandler
from pyanaconda.ui.lib.payload import find_potential_hdiso_sources, get_hdiso_source_info, \
    get_hdiso_source_description
from pyanaconda.ui.lib.subscription import switch_source

log = get_module_logger(__name__)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

__all__ = ["SourceSpoke"]


class SourceSpoke(NormalSpoke, GUISpokeInputCheckHandler, SourceSwitchHandler):
    """
       .. inheritance-diagram:: SourceSpoke
          :parts: 3
    """
    builderObjects = ["partitionStore", "sourceWindow", "dirImage"]
    mainWidgetName = "sourceWindow"
    uiFile = "spokes/installation_source.glade"
    category = SoftwareCategory

    icon = "media-optical-symbolic"
    title = CN_("GUI|Spoke", "_Installation Source")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "software-source-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run for any non-package payload."""
        if not NormalSpoke.should_run(environment, data):
            return False

        return context.payload_type == PAYLOAD_TYPE_DNF

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        GUISpokeInputCheckHandler.__init__(self)
        SourceSwitchHandler.__init__(self)

        self._current_iso_file = None
        self._ready = False
        self._error = None
        self._proxy_url = ""
        self._proxy_change = False
        self._cdrom = None

        self._updates_enabled = False
        self._updates_change = False

        self._network_module = NETWORK.get_proxy()
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)

    def apply(self):
        source_changed = self._update_payload_source()
        repo_changed = self._additional_repositories.apply()
        source_proxy = self.payload.get_source_proxy()
        cdn_source = source_proxy.Type == SOURCE_TYPE_CDN
        # If CDN is the current installation source but no subscription is
        # attached there is no need to refresh the installation source,
        # as without the subscription tokens the refresh would fail anyway.
        if cdn_source and not self.subscribed:
            log.debug("CDN source but no subscribtion attached - skipping payload restart.")
        elif source_changed or repo_changed or self._error:
            payloadMgr.start(self.payload)
        else:
            log.debug("Nothing has changed - skipping payload restart.")

        self.clear_info()

    def _update_payload_source(self):
        """ Check to see if the install method has changed.

            :returns: True if it changed, False if not
            :rtype: bool
        """
        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        if self._cdn_button.get_active():
            if source_type == SOURCE_TYPE_CDN:
                return False
            switch_source(self.payload, SOURCE_TYPE_CDN)
        elif self._cdrom_button.get_active():
            if not self._cdrom:
                return False

            if source_type == SOURCE_TYPE_CDROM:
                # XXX maybe we should always redo it for cdrom in case they
                # switched disks
                return False

            self.set_source_cdrom()
        elif self._dracut_button.get_active():
            if source_type == SOURCE_TYPE_REPO_PATH:
                return False
            self.set_source_dracut()
        elif self._hmc_button.get_active():
            if source_type == SOURCE_TYPE_HMC:
                return False

            self.set_source_hmc()
        elif self._iso_button.get_active():
            # If the user didn't select a partition (not sure how that would
            # happen) or didn't choose a directory (more likely), then return
            # as if they never did anything.
            partition = self._get_selected_partition()
            iso_file = self._current_iso_file

            if not partition or not iso_file:
                return False

            if source_type == SOURCE_TYPE_HDD \
                    and source_proxy.GetDevice() == partition \
                    and source_proxy.GetISOFile() == iso_file:
                return False

            self.set_source_hdd_iso(partition, iso_file)
        elif self._mirror_active():
            if source_type == SOURCE_TYPE_CLOSEST_MIRROR \
                    and self.payload.is_ready() \
                    and not self._proxy_change \
                    and not self._updates_change:
                return False

            self.set_source_closest_mirror(self._updates_enabled)
        elif self._ftp_active():
            url = self._url_entry.get_text().strip()
            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  dnf will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            if not url.startswith("ftp://"):
                url = "ftp://" + url

            if source_type == SOURCE_TYPE_URL and not self._proxy_change:
                repo_configuration = RepoConfigurationData.from_structure(
                    source_proxy.Configuration
                )

                if repo_configuration.url == url:
                    return False

            self.set_source_url(url, proxy=self._proxy_url)
        elif self._http_active():
            url = self._url_entry.get_text().strip()
            # If the user didn't fill in the URL entry, just return as if they
            # selected nothing.
            if url == "":
                return False

            # Make sure the URL starts with the protocol.  dnf will want that
            # to know how to fetch, and the refresh method needs that to know
            # which element of the combo to default to should this spoke be
            # revisited.
            elif (self._protocol_combo_box.get_active_id() == PROTOCOL_HTTP
                  and not url.startswith("http://")):
                url = "http://" + url
            elif (self._protocol_combo_box.get_active_id() == PROTOCOL_HTTPS
                  and not url.startswith("https://")):
                url = "https://" + url

            url_type = self._url_type_combo_box.get_active_id()

            if source_type == SOURCE_TYPE_URL and not self._proxy_change:
                repo_configuration = RepoConfigurationData.from_structure(
                    source_proxy.Configuration
                )

                if repo_configuration.url == url \
                        and repo_configuration.type == url_type:
                    return False

            self.set_source_url(url, url_type, proxy=self._proxy_url)
        elif self._nfs_active():
            url = self._url_entry.get_text().strip()
            opts = self.builder.get_object("nfsOptsEntry").get_text() or ""

            if url == "":
                return False

            try:
                server, directory = url.split(":", 2)
            except ValueError as e:
                log.error("ValueError: %s", e)
                self._error = _(
                    "Failed to set up installation source; "
                    "check the NFS configuration."
                )
                return

            if source_type == SOURCE_TYPE_NFS:
                configuration = RepoConfigurationData.from_structure(
                    source_proxy.Configuration
                )

                if configuration.url == create_nfs_url(server, directory, opts):
                    return False

            self.set_source_nfs(server, directory, opts)

        self._proxy_change = False
        self._updates_change = False

        return True

    @property
    def completed(self):
        """Is the spoke complete?

        WARNING: This can be called before _initialize is done, make sure that it
        doesn't access things that are not setup (eg. payload.*) until it is ready
        """
        source_proxy = self.payload.get_source_proxy()
        if source_proxy.Type == SOURCE_TYPE_CDN:
            return True

        return self.ready and not self._error and self.payload.is_ready()

    @property
    def mandatory(self):
        return True

    @property
    def ready(self):
        return (self._ready and
                not thread_manager.get(constants.THREAD_PAYLOAD) and
                not thread_manager.get(constants.THREAD_SOFTWARE_WATCHER) and
                not thread_manager.get(constants.THREAD_CHECK_SOFTWARE))

    @property
    def subscribed(self):
        """Report if the system is currently subscribed.

        NOTE: This will be always False when the Subscription
              module is no available.

        :return: True if subscribed, False otherwise
        :rtype: bool
        """
        subscribed = False
        if is_module_available(SUBSCRIPTION):
            subscription_proxy = SUBSCRIPTION.get_proxy()
            subscribed = subscription_proxy.IsSubscriptionAttached
        return subscribed

    @property
    def status(self):
        # When CDN is selected as installation source and system
        # is not yet subscribed, the automatic repo refresh will
        # fail. This is expected as CDN can't be used until the
        # system has been registered. So prevent the error
        # message and show CDN is used instead. If CDN still
        # fails after registration, the regular error message
        # will be displayed.
        source_proxy = self.payload.get_source_proxy()
        cdn_source = source_proxy.Type == SOURCE_TYPE_CDN

        if cdn_source and not self.subscribed:
            source_proxy = self.payload.get_source_proxy()
            return source_proxy.Description

        if thread_manager.get(constants.THREAD_CHECK_SOFTWARE):
            return _(PAYLOAD_STATUS_CHECKING_SOFTWARE)

        if not self.ready:
            return _(PAYLOAD_STATUS_SETTING_SOURCE)

        if not self.completed:
            return _(PAYLOAD_STATUS_INVALID_SOURCE)

        source_proxy = self.payload.get_source_proxy()
        return source_proxy.Description

    def _grab_objects(self):
        self._cdrom_button = self.builder.get_object("cdromRadioButton")
        self._cdrom_box = self.builder.get_object("cdromBox")
        self._cdrom_device_label = self.builder.get_object("cdromDeviceLabel")
        self._cdrom_label = self.builder.get_object("cdromLabel")
        self._dracut_button = self.builder.get_object("dracutRadioButton")
        self._cdn_button = self.builder.get_object("cdnRadioButton")
        self._hmc_button = self.builder.get_object("hmcRadioButton")
        self._iso_button = self.builder.get_object("isoRadioButton")
        self._iso_combo = self.builder.get_object("isoPartitionCombo")
        self._iso_box = self.builder.get_object("isoBox")
        self._network_button = self.builder.get_object("networkRadioButton")
        self._network_box = self.builder.get_object("networkBox")

        self._url_entry = self.builder.get_object("urlEntry")
        self._protocol_combo_box = self.builder.get_object("protocolComboBox")
        self._iso_chooser_button = self.builder.get_object("isoChooserButton")

        # Attach a validator to the URL entry. Start it as disabled, and it will be
        # enabled/disabled as entry sensitivity is enabled/disabled.
        self._url_check = self.add_check(self._url_entry, self._check_url_entry)
        self._url_check.enabled = False

        self._url_type_combo_box = self.builder.get_object("urlTypeComboBox")
        self._url_type_label = self.builder.get_object("urlTypeLabel")

        self._updates_radio_button = self.builder.get_object("updatesRadioButton")

        self._verify_iso_button = self.builder.get_object("verifyIsoButton")

        # updates option container
        self._updates_box = self.builder.get_object("updatesBox")

        self._proxy_button = self.builder.get_object("proxyButton")
        self._nfs_opts_box = self.builder.get_object("nfsOptsBox")

        # Connect scroll events on the viewport with focus events on the box
        main_viewport = self.builder.get_object("mainViewport")
        main_box = self.builder.get_object("mainBox")
        main_box.set_focus_vadjustment(Gtk.Scrollable.get_vadjustment(main_viewport))

        # Include the section with additional repositories.
        self._additional_repositories = AdditionalRepositoriesSection(
            payload=self.payload,
            window=self.window
        )

    def initialize(self):
        NormalSpoke.initialize(self)
        self.initialize_start()

        self._grab_objects()
        self._initialize_closest_mirror()

        # I shouldn't have to do this outside GtkBuilder, but it really doesn't
        # want to let me pass in user data.
        # See also: https://bugzilla.gnome.org/show_bug.cgi?id=727919
        self._cdrom_button.connect("toggled", self.on_source_toggled, self._cdrom_box)
        self._dracut_button.connect("toggled", self.on_source_toggled, None)
        self._cdn_button.connect("toggled", self.on_source_toggled, None)
        self._hmc_button.connect("toggled", self.on_source_toggled, None)
        self._iso_button.connect("toggled", self.on_source_toggled, self._iso_box)
        self._iso_combo.connect("changed", self._on_iso_combo_changed)
        self._network_button.connect("toggled", self.on_source_toggled, self._network_box)
        self._network_button.connect("toggled", self._update_url_entry_check)

        # Show or hide the updates option based on the configuration
        if conf.payload.updates_repositories:
            really_show(self._updates_box)
        else:
            really_hide(self._updates_box)

        # Register callbacks to signals of the payload manager.
        payloadMgr.started_signal.connect(self._on_payload_started)
        payloadMgr.stopped_signal.connect(self._on_payload_stopped)
        payloadMgr.failed_signal.connect(self._on_payload_failed)
        payloadMgr.succeeded_signal.connect(self._on_payload_succeeded)

        # It is possible that the payload manager is finished by now. In that case,
        # trigger the failed callback manually to set up the error messages.
        if not payloadMgr.is_running and not payloadMgr.report.is_valid():
            self._on_payload_failed()

        # Report progress messages of the payload manager.
        payloadMgr.progress_changed_signal.connect(self._on_payload_progress_changed)

        # Start the thread last so that we are sure initialize_done() is really called only
        # after all initialization has been done.
        thread_manager.add_thread(
            name=constants.THREAD_SOURCE_WATCHER,
            target=self._initialize
        )

    def _on_payload_started(self):
        # Disable the software selection.
        hubQ.send_not_ready("SoftwareSelectionSpoke")

        # Disable the source selection.
        hubQ.send_not_ready(self.__class__.__name__)

    def _on_payload_failed(self):
        # Set the error message.
        self._error = _(
            "Failed to set up installation sources; "
            "check their configurations."
        )

        if payloadMgr.report.get_messages():
            self._error += _(CLICK_FOR_DETAILS)

    def _on_payload_succeeded(self):
        # Reset the error message.
        self._error = None

    def _on_payload_stopped(self):
        self._ready = True

        # Enable the source selection.
        hubQ.send_ready(self.__class__.__name__)

        # Reset the status of the software selection.
        hubQ.send_ready("SoftwareSelectionSpoke")

    def _on_payload_progress_changed(self, step, message):
        hubQ.send_message(self.__class__.__name__, message)

    def _initialize_closest_mirror(self):
        # If there's no fallback mirror to use, we should just disable that option
        # in the UI.
        if not conf.payload.enable_closest_mirror:
            model = self._protocol_combo_box.get_model()
            itr = model.get_iter_first()
            while itr and model[itr][self._protocol_combo_box.get_id_column()] != PROTOCOL_MIRROR:
                itr = model.iter_next(itr)

            if itr:
                model.remove(itr)

    def _initialize(self):
        thread_manager.wait(constants.THREAD_PAYLOAD)

        # If there is the Subscriptiopn DBus module, make the CDN radio button visible
        if is_module_available(SUBSCRIPTION):
            gtk_call_once(self._cdn_button.set_no_show_all, False)

        # Get the current source.
        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.

        # Enable the local source option if requested.
        if source_type == SOURCE_TYPE_REPO_PATH:
            gtk_call_once(self._dracut_button.set_no_show_all, False)
        # Enable the CD-ROM option if requested.
        elif source_type == SOURCE_TYPE_CDROM:
            self._cdrom = source_proxy.DeviceName
            self._show_cdrom_box_with_device(self._cdrom)
        # Enable the local source option if available.
        elif verify_valid_repository(DRACUT_REPO_DIR):
            gtk_call_once(self._dracut_button.set_no_show_all, False)
        # Enable the auto-detected CD-ROM option if available.
        elif not flags.automatedInstall:
            self._cdrom = find_optical_install_media()
            self._show_cdrom_box_with_device(self._cdrom)

        # Enable the HDD option.
        if source_type == SOURCE_TYPE_HDD:
            self._current_iso_file = source_proxy.GetISOFile() or None

            if not self._current_iso_file:
                # Installation from an expanded installation tree.
                configuration = RepoConfigurationData.from_structure(
                    source_proxy.Configuration
                )
                device, path = parse_hdd_url(configuration.url)
                self._show_hdd_box(device, path)

        # Enable the SE/HMC option.
        if source_type == SOURCE_TYPE_HMC:
            gtk_call_once(self._hmc_button.set_no_show_all, False)

        # Add the mirror manager URL in as the default for HTTP and HTTPS.
        # We'll override this later in the refresh() method, if they've already
        # provided a URL.

        self._ready = True
        # Wait to make sure the other threads are done before sending ready, otherwise
        # the spoke may not be set sensitive by _handleCompleteness in the hub.
        while not self.ready:
            time.sleep(1)

        hubQ.send_ready(self.__class__.__name__)

        # report that the source spoke has been initialized
        self.initialize_done()

    def _show_cdrom_box_with_device(self, device_name):
        if not device_name:
            return

        device_format_data = DeviceFormatData.from_structure(
            self._device_tree.GetFormatData(device_name)
        )
        device_label = device_format_data.attrs.get("label", "")
        self._show_cdrom_box(device_name, device_label)

    def _show_cdrom_box(self, device_name, device_label):
        fire_gtk_action(self._cdrom_device_label.set_text, _("Device: %s") % device_name)
        fire_gtk_action(self._cdrom_label.set_text, _("Label: %s") % device_label)

        gtk_call_once(self._cdrom_box.set_no_show_all, False)
        gtk_call_once(self._cdrom_button.set_no_show_all, False)

    def _show_hdd_box(self, device_name, source_path):
        """Use the CD-ROM box to display a HDD source without an ISO image."""
        fire_gtk_action(self._cdrom_device_label.set_text, _("Device: %s") % device_name)
        fire_gtk_action(self._cdrom_label.set_text, _("Path: %s") % source_path)

        gtk_call_once(self._cdrom_box.set_no_show_all, False)
        gtk_call_once(self._cdrom_button.set_no_show_all, False)

    def refresh(self):
        NormalSpoke.refresh(self)

        # Clear the additional repositories.
        self._additional_repositories.clear()

        # Find all hard drive partitions that could hold an ISO and add each
        # to the partitionStore.  This has to be done here because if the user
        # has done partitioning first, they may have blown away partitions
        # found during _initialize on the partitioning spoke.
        store = self.builder.get_object("partitionStore")
        store.clear()

        added = False

        active_idx = 0
        active_name = None

        source_proxy = self.payload.get_source_proxy()
        source_type = source_proxy.Type

        if source_type == SOURCE_TYPE_HDD:
            active_name = source_proxy.GetDevice()

        for idx, device_name in enumerate(find_potential_hdiso_sources()):
            device_info = get_hdiso_source_info(self._device_tree, device_name)
            device_desc = get_hdiso_source_description(device_info)
            store.append([device_name, device_desc])

            if device_name == active_name:
                active_idx = idx

            added = True

        # Again, only display these widgets if an HDISO source was found.
        self._iso_box.set_no_show_all(not added)
        self._iso_box.set_visible(added)
        self._iso_button.set_no_show_all(not added)
        self._iso_button.set_visible(added)

        if added:
            self._iso_combo.set_active(active_idx)

        # We defaults and if the method tells us something different later, we can change it.
        self._protocol_combo_box.set_active_id(PROTOCOL_MIRROR)
        self._url_type_combo_box.set_active_id(URL_TYPE_BASEURL)
        self._updates_enabled = False

        if source_type == SOURCE_TYPE_CDN:
            self._cdn_button.set_active(True)
        elif source_type == SOURCE_TYPE_URL:
            self._network_button.set_active(True)

            # Get the current configuration.
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.Configuration
            )

            proto = repo_configuration.url
            if proto.startswith("http:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTP)
                length = 7
            elif proto.startswith("https:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTPS)
                length = 8
            elif proto.startswith("ftp:"):
                self._protocol_combo_box.set_active_id(PROTOCOL_FTP)
                length = 6
            else:
                self._protocol_combo_box.set_active_id(PROTOCOL_HTTP)
                length = 0

            self._url_entry.set_text(proto[length:])
            self._update_url_entry_check()
            self._url_type_combo_box.set_active_id(repo_configuration.type)
            self._proxy_url = repo_configuration.proxy
        elif source_type == SOURCE_TYPE_NFS:
            self._network_button.set_active(True)
            self._protocol_combo_box.set_active_id(PROTOCOL_NFS)

            # Get the current URL.
            configuration = RepoConfigurationData.from_structure(
                source_proxy.Configuration
            )
            options, host, path = parse_nfs_url(configuration.url)

            self._url_entry.set_text("{}:{}".format(host, path))
            self._update_url_entry_check()
            self.builder.get_object("nfsOptsEntry").set_text(options or "")
        elif source_type == SOURCE_TYPE_HDD:
            if not self._current_iso_file:
                self._cdrom_button.set_active(True)
            else:
                self._iso_button.set_active(True)
                self._verify_iso_button.set_sensitive(True)

                iso_name = os.path.basename(self._current_iso_file)
                self._iso_chooser_button.set_label(iso_name)
                self._iso_chooser_button.set_use_underline(False)
        elif source_type == SOURCE_TYPE_HMC:
            self._hmc_button.set_active(True)
        elif source_type == SOURCE_TYPE_CDROM:
            # Go with autodetected media if that was provided,
            # otherwise fall back to the closest mirror.
            if not self._cdrom_button.get_no_show_all():
                self._cdrom_button.set_active(True)
            else:
                self._network_button.set_active(True)
        elif source_type == SOURCE_TYPE_REPO_PATH:
            if not self._dracut_button.get_no_show_all():
                self._dracut_button.set_active(True)
            else:
                self._network_button.set_active(True)
        elif source_type == SOURCE_TYPE_CLOSEST_MIRROR:
            self._network_button.set_active(True)
            self._updates_enabled = source_proxy.UpdatesEnabled
        else:
            raise ValueError("Unsupported source type: '{}'".format(source_type))

        self._setup_updates()

        # Some widgets get enabled/disabled/greyed out depending on
        # how others are set up.  We can use the signal handlers to handle
        # that condition here too. Start at the innermost pieces and work
        # outwards

        # First check the protocol combo in the network box
        self._on_protocol_changed()

        # Then simulate changes for the radio buttons, which may override the
        # sensitivities set for the network box.
        #
        # Whichever radio button is selected should have gotten a signal
        # already, but the ones that are not selected need a signal in order
        # to disable the related box.
        self._on_source_toggled(self._cdrom_button, self._cdrom_box)
        self._on_source_toggled(self._dracut_button, None)
        self._on_source_toggled(self._hmc_button, None)
        self._on_source_toggled(self._iso_button, self._iso_box)
        self._on_source_toggled(self._network_button, self._network_box)

        # Set up additional repositories. Wait until the installation source
        # is set up to avoid unwanted removals of treeinfo repositories.
        self._additional_repositories.refresh()

        if not self._network_module.Connected:
            self._network_button.set_sensitive(False)
            self._network_box.set_sensitive(False)

            self.clear_info()
            self.set_warning(_("You need to configure the network to use a network "
                               "installation source."))
        else:
            # network button could be deativated from last visit
            self._network_button.set_sensitive(True)

        # Update the URL entry validation now that we're done messing with sensitivites
        self._update_url_entry_check()

        # Show the info bar with an error message if any.
        # This error message has the highest priority.
        if self._error:
            self.clear_info()
            self.set_warning(self._error)

    def _setup_updates(self):
        """ Setup the state of the No Updates checkbox.

            If closest mirror is not selected, check it.
            If closest mirror is selected, and "updates" repo is enabled,
            uncheck it.
        """
        self._updates_box.set_sensitive(self._mirror_active())
        active = self._mirror_active() and self._updates_enabled
        self._updates_radio_button.set_active(active)

    def _mirror_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_MIRROR and \
            self._network_button.get_active()

    def _http_active(self):
        return self._protocol_combo_box.get_active_id() in (
            PROTOCOL_HTTP,
            PROTOCOL_HTTPS,
            PROTOCOL_MIRROR
        )

    def _ftp_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_FTP

    def _nfs_active(self):
        return self._protocol_combo_box.get_active_id() == PROTOCOL_NFS

    def _get_selected_partition(self):
        """Get a name of the selected partition."""
        store = self.builder.get_object("partitionStore")
        combo = self.builder.get_object("isoPartitionCombo")

        selected = combo.get_active()
        if selected == -1:
            return None
        else:
            return store[selected][0]

    # Input checks

    def _check_url(self, inputcheck, combo):
        # Network is not up, don't check urls.
        if not self._network_module.Connected:
            return InputCheck.CHECK_OK

        url_string = self.get_input(inputcheck.input_obj).strip()
        protocol = combo.get_active_id()

        # If this is HTTP/HTTPS/FTP, use the URL_PARSE regex
        if protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP):
            if not url_string:
                return _("URL is empty")

            m = URL_PARSE.match(url_string)
            if not m:
                return _("Invalid URL")

            # Matching protocols in the URL should already have been removed
            # by _remove_url_prefix. If there's still one there, it's wrong.
            url_protocol = m.group('protocol')
            if url_protocol:
                return _("Protocol in URL does not match selected protocol")
        elif protocol == PROTOCOL_NFS:
            if not url_string:
                return _("NFS server is empty")

            # Check first overall validity of format
            if url_string.count(":") != 1:
                return _("Invalid NFS server, exactly one colon ':' must be present "
                         "between host and directory")

            # Make sure the part before the colon looks like a hostname,
            # and that the path is not empty
            host, _colon, path = url_string.partition(':')

            if not re.match('^' + HOSTNAME_PATTERN_WITHOUT_ANCHORS + '$', host):
                return _("Invalid host name")

            if not path:
                return _("Remote directory is required")

        return InputCheck.CHECK_OK

    def _check_url_entry(self, inputcheck):
        return self._check_url(inputcheck, self._protocol_combo_box)

    # Update the check on urlEntry when the sensitity or selected protocol changes
    def _update_url_entry_check(self, *args):
        self._url_check.enabled = self._url_entry.is_sensitive()
        self._url_check.update_check_status()

        # Force a status update to clear any disabled errors
        self.set_status(self._url_check)

    # Signal handlers.
    def on_source_toggled(self, button, relatedBox):
        # When a radio button is clicked, this handler gets called for both
        # the newly enabled button as well as the previously enabled (now
        # disabled) button.
        self._on_source_toggled(button, relatedBox)
        self._additional_repositories.remove_treeinfo_repositories()

    def _on_iso_combo_changed(self, combo):
        store = self.builder.get_object("partitionStore")
        idx = combo.get_active()
        if idx != -1:
            combo.set_tooltip_text(store[idx][1])

    def _on_source_toggled(self, button, relatedBox):
        enabled = button.get_active()

        if relatedBox:
            relatedBox.set_sensitive(enabled)

        self._setup_updates()

    def on_back_clicked(self, button):
        """If any input validation checks failed, keep the user on the screen.
           Otherwise, do the usual thing."""
        self.clear_info()

        if not self._additional_repositories.validate():
            return

        NormalSpoke.on_back_clicked(self, button)

    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)", self._error, args)
        messages = payloadMgr.report.get_messages()

        if not messages:
            return

        dlg = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            message_format="\n".join(messages)
        )
        dlg.set_decorated(False)

        with self.main_window.enlightbox(dlg):
            dlg.run()
            dlg.destroy()

    def on_chooser_clicked(self, button):
        # If the chooser has been run once before, we should make it default to
        # the previously selected file.
        dialog = IsoChooser(self.data, current_file=self._current_iso_file)

        with self.main_window.enlightbox(dialog.window):
            iso_file = dialog.run(self._get_selected_partition())

        if iso_file and iso_file.endswith(".iso"):
            self._current_iso_file = join_paths("/", iso_file)

            button.set_label(os.path.basename(iso_file))
            button.set_use_underline(False)

            self._verify_iso_button.set_sensitive(True)
            self._additional_repositories.remove_treeinfo_repositories()

    def on_proxy_clicked(self, button):
        dialog = ProxyDialog(self.data, self._proxy_url)
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh()
            dialog.run()

        if self._proxy_url != dialog.proxy_url:
            self._proxy_change = True
            self._proxy_url = dialog.proxy_url

    def on_verify_iso_clicked(self, button):
        partition = self._get_selected_partition()
        iso_file = self._current_iso_file

        if not partition or not iso_file:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
            path = payload_utils.get_device_path(partition)

            # FIXME: Use a unique mount point.
            mounts = payload_utils.get_mount_paths(path)
            mountpoint = None
            # We have to check both ISO_DIR and the DRACUT_ISODIR because we
            # still reference both, even though /mnt/install is a symlink to
            # /run/install.  Finding mount points doesn't handle the symlink
            if constants.ISO_DIR not in mounts and constants.DRACUT_ISODIR not in mounts:
                # We're not mounted to either location, so do the mount
                mountpoint = constants.ISO_DIR
                payload_utils.mount_device(partition, mountpoint)

            dialog.run(join_paths(constants.ISO_DIR, iso_file))

            if not mounts:
                payload_utils.unmount_device(partition, mountpoint)

    def on_verify_media_clicked(self, button):
        if not self._cdrom:
            return

        dialog = MediaCheckDialog(self.data)
        with self.main_window.enlightbox(dialog.window):
            dialog.run("/dev/" + self._cdrom)

    def on_protocol_changed(self, combo):
        self._on_protocol_changed()
        self._additional_repositories.remove_treeinfo_repositories()

    def _on_protocol_changed(self):
        # Only allow the URL entry to be used if we're using an HTTP/FTP
        # method that's not the mirror list, or an NFS method.
        self._url_entry.set_sensitive(self._http_active() or self._ftp_active() or
                                      self._nfs_active())

        # Only allow these widgets to be shown if it makes sense for the
        # the currently selected protocol.
        self._proxy_button.set_sensitive(self._http_active() or self._mirror_active())
        self._nfs_opts_box.set_visible(self._nfs_active())
        self._url_type_combo_box.set_visible(self._http_active())
        self._url_type_label.set_visible(self._http_active())
        self._setup_updates()

        # Any changes to the protocol combo box also need to update the checks.
        # Emitting the urlEntry 'changed' signal will see if the entered URL
        # contains the protocol that's just been selected and strip it if so;
        # _update_url_entry_check() does the other validity checks.
        self._on_urlEtry_changed(self._url_entry)
        self._update_url_entry_check()

    def _remove_url_prefix(self, editable, combo, handler):
        # If there is a protocol in the URL, and the protocol matches the
        # combo box, just remove it. This makes it more convenient to paste
        # in URLs. It'll probably freak out people who are typing out http://
        # in the box themselves, but why would you do that?  Don't do that.

        combo_protocol = combo.get_active_id()
        if combo_protocol in (PROTOCOL_HTTP, PROTOCOL_HTTPS, PROTOCOL_FTP):
            url_string = editable.get_text()
            m = URL_PARSE.match(url_string)
            if m:
                url_protocol = m.group('protocol')
                if (url_protocol == 'http://' and combo_protocol == PROTOCOL_HTTP) or \
                        (url_protocol == 'https://' and combo_protocol == PROTOCOL_HTTPS) or \
                        (url_protocol == 'ftp://' and combo_protocol == PROTOCOL_FTP):
                    # URL protocol matches. Block the changed signal and remove it
                    with blockedHandler(editable, handler):
                        editable.set_text(url_string[len(url_protocol):])

    def on_urlEntry_changed(self, editable, data=None):
        # Check for and remove a URL prefix that matches the protocol dropdown
        self._on_urlEtry_changed(editable)
        self._additional_repositories.remove_treeinfo_repositories()

    def _on_urlEtry_changed(self, editable):
        self._remove_url_prefix(editable, self._protocol_combo_box, self.on_urlEntry_changed)

    def on_updatesRadioButton_toggled(self, button):
        """Toggle the enable state of the updates repo."""
        active = self._updates_radio_button.get_active()
        self._updates_enabled = active
        self._updates_change = True
