# Progress hub classes
#
# Copyright (C) 2011-2013  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from __future__ import division

from gi.repository import GLib, Gtk

import itertools
import os
import sys
import glob

from pyanaconda.i18n import _, C_
from pyanaconda.localization import find_best_locale_match
from pyanaconda.product import productName
from pyanaconda.flags import flags
from pyanaconda import iutil
from pyanaconda.constants import THREAD_INSTALL, THREAD_CONFIGURATION, DEFAULT_LANG, IPMI_FINISHED
from pykickstart.constants import KS_SHUTDOWN, KS_REBOOT

from pyanaconda.ui.gui.hubs import Hub
from pyanaconda.ui.gui.utils import gtk_action_nowait, gtk_call_once

__all__ = ["ProgressHub"]

class ProgressHub(Hub):
    builderObjects = ["progressWindow"]
    mainWidgetName = "progressWindow"
    uiFile = "hubs/progress.glade"
    helpFile = "ProgressHub.xml"

    def __init__(self, data, storage, payload, instclass):
        Hub.__init__(self, data, storage, payload, instclass)

        self._totalSteps = 0
        self._currentStep = 0
        self._configurationDone = False

        self._rnotes_id = None

    def _do_configuration(self, widget = None, reenable_ransom = True):
        from pyanaconda.install import doConfiguration
        from pyanaconda.threads import threadMgr, AnacondaThread

        assert self._configurationDone == False

        self._configurationDone = True

        # Disable all personalization spokes
        self.builder.get_object("progressWindow-scroll").set_sensitive(False)

        if reenable_ransom:
            self._start_ransom_notes()

        self._restart_spinner()

        GLib.timeout_add(250, self._update_progress, self._configuration_done)
        threadMgr.add(AnacondaThread(name=THREAD_CONFIGURATION, target=doConfiguration,
                                     args=(self.storage, self.payload, self.data, self.instclass)))

    def _start_ransom_notes(self):
        # Adding this as a timeout below means it'll get called after 60
        # seconds, so we need to do the first call manually.
        self._cycle_rnotes()
        self._rnotes_id = GLib.timeout_add_seconds(60, self._cycle_rnotes)

    def _update_progress(self, callback = None):
        from pyanaconda.progress import progressQ
        import Queue

        q = progressQ.q

        # Grab all messages may have appeared since last time this method ran.
        while True:
            # Attempt to get a message out of the queue for how we should update
            # the progress bar.  If there's no message, don't error out.
            try:
                (code, args) = q.get(False)
            except Queue.Empty:
                break

            if code == progressQ.PROGRESS_CODE_INIT:
                self._init_progress_bar(args[0])
            elif code == progressQ.PROGRESS_CODE_STEP:
                self._step_progress_bar()
            elif code == progressQ.PROGRESS_CODE_MESSAGE:
                self._update_progress_message(args[0])
            elif code == progressQ.PROGRESS_CODE_COMPLETE:
                q.task_done()

                # we are done, stop the progress indication
                gtk_call_once(self._progressBar.set_fraction, 1.0)
                gtk_call_once(self._progressLabel.set_text, _("Complete!"))
                gtk_call_once(self._spinner.stop)
                gtk_call_once(self._spinner.hide)

                if callback:
                    callback()

                # There shouldn't be any more progress bar updates, so return False
                # to indicate this method should be removed from the idle loop.
                return False
            elif code == progressQ.PROGRESS_CODE_QUIT:
                sys.exit(args[0])

            q.task_done()

        return True


    def _configuration_done(self):
        # Configuration done, remove ransom notes timer
        # and switch to the Reboot page

        GLib.source_remove(self._rnotes_id)
        self._progressNotebook.set_current_page(1)

        iutil.ipmi_report(IPMI_FINISHED)

        # kickstart install, continue automatically if reboot or shutdown selected
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            self.window.emit("continue-clicked")

    def _install_done(self):
        # package installation done, check personalization spokes
        # and start the configuration step if all is ready
        if not self._inSpoke and self.continuePossible:
            self._do_configuration(reenable_ransom = False)

        else:
            # some mandatory spokes are not ready
            # switch to configure and finish page
            GLib.source_remove(self._rnotes_id)
            self._progressNotebook.set_current_page(0)

    def _do_globs(self, path):
        return glob.glob(path + "/*.png") + \
               glob.glob(path + "/*.jpg") + \
               glob.glob(path + "/*.svg")

    def _get_rnotes(self):
        # We first look for rnotes in paths containing the language, then in
        # directories without the language component.  You know, just in case.

        paths = ["/tmp/updates/pixmaps/rnotes/",
                 "/tmp/product/pixmaps/rnotes/",
                 "/usr/share/anaconda/pixmaps/rnotes/"]

        all_lang_pixmaps = []
        for path in paths:
            all_lang_pixmaps += self._do_globs(path + "/*")

        pixmap_langs = [pixmap.split(os.path.sep)[-2] for pixmap in all_lang_pixmaps]
        best_lang = find_best_locale_match(os.environ["LANG"], pixmap_langs)

        if not best_lang:
            # nothing found, try the default language
            best_lang = find_best_locale_match(DEFAULT_LANG, pixmap_langs)

        if not best_lang:
            # nothing found even for the default language, try non-localized rnotes
            non_localized = []
            for path in paths:
                non_localized += self._do_globs(path)

            return non_localized

        best_lang_pixmaps = []
        for path in paths:
            best_lang_pixmaps += self._do_globs(path + best_lang)

        return best_lang_pixmaps

    def _cycle_rnotes(self):
        # Change the ransom notes image every minute by grabbing the next
        # image's filename.  Note that self._rnotesPages is an infinite list,
        # so this will cycle through the images indefinitely.
        try:
            nxt = next(self._rnotesPages)
        except StopIteration:
            # there are no rnotes
            pass
        else:
            self._progressNotebook.set_current_page(nxt)

        return True

    def initialize(self):
        Hub.initialize(self)

        if flags.livecdInstall:
            continueText = self.builder.get_object("rebootLabel")
            continueText.set_text(_("%s is now successfully installed on your system and ready "
                                    "for you to use!  When you are ready, reboot your system to start using it!"))
            continueText.set_line_wrap(True)
            self.window.get_continue_button().set_label(C_("GUI|Progress", "_Quit"))

        self._progressBar = self.builder.get_object("progressBar")
        self._progressLabel = self.builder.get_object("progressLabel")
        self._progressNotebook = self.builder.get_object("progressNotebook")
        self._spinner = self.builder.get_object("progressSpinner")

        lbl = self.builder.get_object("configurationLabel")
        lbl.set_text(_("%s is now successfully installed, but some configuration still needs to be done.\n"
            "Finish it and then click the Finish configuration button please.") %
            productName)

        lbl = self.builder.get_object("rebootLabel")
        lbl.set_text(_("%s is now successfully installed and ready for you to use!\n"
                "Go ahead and reboot to start using it!") % productName)

        rnotes = self._get_rnotes()
        # Get the start of the pages we're about to add to the notebook
        rnotes_start = self._progressNotebook.get_n_pages()
        if rnotes:
            # Add a new page in the notebook for each ransom note image.
            for f in rnotes:
                img = Gtk.Image.new_from_file(f)
                img.show()
                self._progressNotebook.append_page(img, None)

            # An infinite list of the page numbers containing ransom notes images.
            self._rnotesPages = itertools.cycle(range(rnotes_start,
                self._progressNotebook.get_n_pages()))
        else:
            # Add a blank page to the notebook and we'll just cycle to that
            # over and over again.
            blank = Gtk.Box()
            blank.show()
            self._progressNotebook.append_page(blank, None)
            self._rnotesPages = itertools.cycle([rnotes_start])

    def refresh(self):
        from pyanaconda.install import doInstall
        from pyanaconda.threads import threadMgr, AnacondaThread

        Hub.refresh(self)

        self._start_ransom_notes()
        GLib.timeout_add(250, self._update_progress, self._install_done)
        threadMgr.add(AnacondaThread(name=THREAD_INSTALL, target=doInstall,
                                     args=(self.storage, self.payload, self.data, self.instclass)))

    def _updateContinueButton(self):
        if self._configurationDone:
            self.window.set_may_continue(self.continuePossible)
        else:
            self.builder.get_object("configureButton").set_sensitive(self.continuePossible)

    def _init_progress_bar(self, steps):
        self._totalSteps = steps
        self._currentStep = 0

        gtk_call_once(self._progressBar.set_fraction, 0.0)

    def _step_progress_bar(self):
        if not self._totalSteps:
            return

        self._currentStep += 1
        gtk_call_once(self._progressBar.set_fraction, self._currentStep/self._totalSteps)

    def _update_progress_message(self, message):
        if not self._totalSteps:
            return

        gtk_call_once(self._progressLabel.set_text, message)

    @gtk_action_nowait
    def _restart_spinner(self):
        self._spinner.show()
        self._spinner.start()
