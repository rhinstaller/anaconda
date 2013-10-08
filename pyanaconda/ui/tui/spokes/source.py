# Source repo text spoke
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#

from pyanaconda.flags import flags
from pyanaconda.ui.tui.spokes import EditTUISpoke
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PayloadError, MetadataError
from pyanaconda.i18n import _
from pyanaconda.image import opticalInstallMedia

from pyanaconda.constants import THREAD_SOURCE_WATCHER, THREAD_SOFTWARE_WATCHER, THREAD_PAYLOAD
from pyanaconda.constants import THREAD_PAYLOAD_MD, THREAD_STORAGE, THREAD_CHECK_SOFTWARE
from pyanaconda.constants_text import INPUT_PROCESSED

import re

import logging
LOG = logging.getLogger("anaconda")


__all__ = ["SourceSpoke"]

class SourceSpoke(EditTUISpoke):
    """ Spoke used to customize the install source repo. """
    title = _("Installation source")
    category = "software"

    _protocols = (_("Closest mirror"), "http://", "https://", "ftp://", "nfs")

    # default to 'closest mirror', as done in the GUI
    _selection = 1

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._ready = False
        self.errors = []
        self._cdrom = None

    def initialize(self):
        EditTUISpoke.initialize(self)

        threadMgr.add(AnacondaThread(name=THREAD_SOURCE_WATCHER,
                                     target=self._initialize))

    def _initialize(self):
        """ Private initialize. """
        threadMgr.wait(THREAD_STORAGE)
        threadMgr.wait(THREAD_PAYLOAD)
        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if self.data.method.method == "cdrom":
            self._cdrom = self.payload.install_device
        elif not flags.automatedInstall:
            self._cdrom = opticalInstallMedia(self.storage.devicetree)

        self._ready = True

    def _repo_status(self):
        """ Return a string describing repo url or lack of one. """
        if self.data.method.method == "url":
            return self.data.method.url or self.data.method.mirrorlist
        elif self.data.method.method == "nfs":
            return _("NFS server %s") % self.data.method.server
        elif self.data.method.method == "cdrom":
            return _("CD/DVD drive")
        elif self.payload.baseRepo:
            return _("Closest mirror")
        else:
            return _("Nothing selected")

    @property
    def status(self):
        if self.errors:
            return _("Error setting up software source")
        elif not self._ready:
            return _("Processing...")
        else:
            return self._repo_status()

    def _update_summary(self):
        """ Update screen with a summary. Show errors if there are any. """
        summary = (_("Repo URL set to: %s") % self._repo_status())

        if self.errors:
            summary = summary + "\n" + "\n".join(self.errors)

        return summary

    @property
    def completed(self):
        if flags.automatedInstall and (not self.data.method.method or not self.payload.baseRepo):
            return False
        else:
            return not self.errors and self.ready and (self.data.method.method or self.payload.baseRepo)

    def refresh(self, args=None):
        EditTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD_MD)

        _methods = [_("CD/DVD"), _("Network")]
        if args == 2:
            text = [TextWidget(p) for p in self._protocols]
        else:
            self._window += [TextWidget(_("Choose an installation source type."))]
            text = [TextWidget(m) for m in _methods]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # gnarl and mangle all of our widgets so things look pretty on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]

        displayed = ColumnWidget([(78, choices)], 1)
        self._window.append(displayed)

        return True

    def input(self, args, key):
        """ Handle the input; this decides the repo protocol. """
        try:
            num = int(key)
        except ValueError:
            return key

        if args == 2:
            # network install
            self._selection = num
            if self._selection == 1:
                # closest mirror
                self.data.method.method = None
                self.apply()
                self.close()
                return INPUT_PROCESSED
            elif self._selection in range(2, 5):
                self.data.method.method = "url"
                newspoke = SpecifyRepoSpoke(self.app, self.data, self.storage,
                                          self.payload, self.instclass, self._selection)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.close()
                return INPUT_PROCESSED
            elif self._selection == 5:
                # nfs
                self.data.method.method = "nfs"
                newspoke = SpecifyNFSRepoSpoke(self.app, self.data, self.storage,
                                        self.payload, self.instclass, self._selection, self.errors)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.close()
                return INPUT_PROCESSED
        else:
            if num == 1:
                # iso selected, just set some vars and return to main hub
                self.data.method.method = "cdrom"
                self.payload.install_device = self._cdrom
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                self.app.switch_screen(self, num)
        return INPUT_PROCESSED

    def getRepoMetadata(self):
        """ Pull down yum repo metadata """
        try:
            self.payload.updateBaseRepo(fallback=False, checkmount=False)
        except (OSError, PayloadError) as err:
            LOG.error("Error: %s", err)
            self.errors.append(_("Failed to set up installation source"))
        else:
            self.payload.gatherRepoMetadata()
            self.payload.release()
            if not self.payload.baseRepo:
                self.errors.append(_("Error downloading package metadata"))
            else:
                try:
                    # pylint: disable-msg=W0104
                    self.payload.environments
                    # pylint: disable-msg=W0104
                    self.payload.groups
                except MetadataError:
                    self.errors.append(_("No installation source available"))

    @property
    def ready(self):
        """ Check if the spoke is ready. """
        return (self._ready and
                not threadMgr.get(THREAD_PAYLOAD_MD) and
                not threadMgr.get(THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE))

    def apply(self):
        """ Execute the selections made. """
        threadMgr.add(AnacondaThread(name=THREAD_PAYLOAD_MD,
                                     target=self.getRepoMetadata))

class SpecifyRepoSpoke(EditTUISpoke):
    """ Specify the repo URL here if closest mirror not selected. """
    title = _("Specify Repo Options")
    category = "software"

    edit_fields = [
        Entry(_("Repo URL"), "url", re.compile(".*$"), True)
        ]

    def __init__(self, app, data, storage, payload, instclass, selection):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.selection = selection
        self.args = self.data.method

    def refresh(self, args=None):
        """ Refresh window. """
        return EditTUISpoke.refresh(self, args)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply all of our changes. """
        if self.selection == 2 and not self.args.url.startswith("http://"):
            self.data.method.url = "http://" + self.args.url
        elif self.selection == 3 and not self.args.url.startswith("https://"):
            self.data.method.url = "https://" + self.args.url
        elif self.selection == 4 and not self.args.url.startswith("ftp://"):
            self.data.method.url = "ftp://" + self.args.url
        else:
            # protocol either unknown or entry already starts with a protocol
            # specification
            self.data.method.url = self.args.url

class SpecifyNFSRepoSpoke(EditTUISpoke):
    """ Specify server and mount opts here if NFS selected. """
    title = _("Specify Repo Options")
    category = "software"

    edit_fields = [
        Entry(_("NFS <server>:/<path>"), "server", re.compile(".*$"), True),
        Entry(_("NFS mount options"), "opts", re.compile(".*$"), True)
    ]

    def __init__(self, app, data, storage, payload, instclass, selection, errors):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.selection = selection
        self.args = self.data.method
        self.errors = errors

    def refresh(self, args=None):
        """ Refresh window. """
        return EditTUISpoke.refresh(self, args)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        if self.args.server == "" or not ':' in self.args.server:
            return False

        if self.args.server.startswith("nfs://"):
            self.args.server = self.args.server.strip("nfs://")

        try:
            (self.data.method.server, self.data.method.dir) = self.args.server.split(":", 2)
        except ValueError as err:
            LOG.error("ValueError: %s", err)
            self.errors.append(_("Failed to set up installation source. Check the source address."))
            return

        self.data.method.opts = self.args.opts or ""
