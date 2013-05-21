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
from pyanaconda.ui.tui.simpleline import CheckboxWidget, TextWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PayloadError, MetadataError
from pyanaconda.i18n import _

from pyanaconda.constants import THREAD_SOURCE_WATCHER, THREAD_SOFTWARE_WATCHER, THREAD_PAYLOAD
from pyanaconda.constants import THREAD_PAYLOAD_MD, THREAD_STORAGE, THREAD_CHECK_SOFTWARE

import re

import logging
LOG = logging.getLogger("anaconda")


__all__ = ["SourceSpoke"]

class SourceSpoke(EditTUISpoke):
    """ Spoke used to customize the install source repo. """
    title = _("Installation source")
    category = "source"

    _protocols = (_("Closest mirror"), "http://", "https://", "ftp://")

    # default to 'closest mirror', as done in the GUI
    _selection = 1

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._ready = False
        self.errors = []

    def initialize(self):
        EditTUISpoke.initialize(self)

        threadMgr.add(AnacondaThread(name=THREAD_SOURCE_WATCHER,
                                     target=self._initialize))

    def _initialize(self):
        """ Private initialize. """
        threadMgr.wait(THREAD_STORAGE)
        threadMgr.wait(THREAD_PAYLOAD)
        self._ready = True

    def _repo_status(self):
        """ Return a string describing repo url or lack of one. """
        if self.data.method.method == "url":
            return self.data.method.url or self.data.method.mirrorlist
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
            return not self.errors and self.ready

    def refresh(self, args=None):
        EditTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD_MD)

        print(_("Choose an installation source type."))

        msg = self._update_summary()

        for num, proto in enumerate(self._protocols):
            box = CheckboxWidget(title="%i) %s" % (num + 1, proto), completed=(num + 1 == self._selection))
            self._window += [box, ""]

        self._window += [TextWidget(msg), ""]

        return True

    def input(self, args, key):
        """ Handle the input; this decides the repo protocol. """
        if key == "c" and self._selection == 1:
            # closest mirror
            self.data.method.method = None
            self.apply()

        if key == "c" and self._selection in range(2, 5):
            self.data.method.method = "url"

            # want to kick off new spoke asking to specify repo
            newspoke = SpecifyRepoSpoke(self.app, self.data, self.storage,
                                        self.payload, self.instclass, self._selection)
            self.app.switch_screen_modal(newspoke)
            self.apply()

        try:
            num = int(key)
            if num in range(1, 5):
                self._selection = num
            return None
        except (ValueError, IndexError):
            return key

    def getRepoMetadata(self):
        """ Pull down yum repo metadata """
        try:
            self.payload.updateBaseRepo(fallback=False, checkmount=False)
        except PayloadError as err:
            LOG.error("PayloadError: %s" % (err,))
            self.errors.append(_("Failed to set up installation source"))
        else:
            self.payload.gatherRepoMetadata()
            self.payload.release()
            if not self.payload.baseRepo:
                self.errors.append(_("Error downloading package metadata"))
            else:
                try:
                    env = self.payload.environments
                    grp = self.payload.groups
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
    category = "source"

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
