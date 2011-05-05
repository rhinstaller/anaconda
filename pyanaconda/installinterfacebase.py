#
# installinterfacebase.py: a baseclass for anaconda interface classes
#
# Copyright (C) 2010  Red Hat, Inc.  All rights reserved.
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
# Author(s): Hans de Goede <hdegoede@redhat.com>

import gettext
import sys

_ = lambda x: gettext.ldgettext("anaconda", x)
P_ = lambda x, y, z: gettext.ldngettext("anaconda", x, y, z)

import logging
log = logging.getLogger("anaconda")

class InstallInterfaceBase(object):
    def __init__(self):
        self._warnedUnusedRaidMembers = []
        self._initLabelAnswers = {}
        self._inconsistentLVMAnswers = {}

    def messageWindow(self, title, text, type="ok", default = None,
             custom_buttons=None,  custom_icon=None):
        raise NotImplementedError

    def detailedMessageWindow(self, title, text, longText=None, type="ok",
                              default=None, custom_icon=None,
                              custom_buttons=[], expanded=False):
        raise NotImplementedError

    def methodstrRepoWindow(self, methodstr, exception):
        """ Called when the repo specified by methodstr could not be found.

            Depending on the interface implementation terminates the program or
            gives user a chance to specify a new repo path it then returns. The
            default implementation is to terminate.
        """
        self.messageWindow(
            _("Error Setting Up Repository"),
            _("The following error occurred while setting up the "
              "installation repository:\n\n%(e)s\n\n"
              "Installation can not continue.")
            % {'e': exception},
            type = "custom",
            custom_icon="info",
            custom_buttons=[_("Exit installer")])
        sys.exit(0)

    def unusedRaidMembersWarning(self, unusedRaidMembers):
        """Warn about unused BIOS RAID members"""
        unusedRaidMembers = \
            filter(lambda m: m not in self._warnedUnusedRaidMembers,
                   unusedRaidMembers)
        if unusedRaidMembers:
            self._warnedUnusedRaidMembers.extend(unusedRaidMembers)
            unusedRaidMembers.sort()
            self.messageWindow(_("Warning"),
                P_("Disk %(unusedRaidMems)s contains BIOS RAID metadata, but is not part of "
                   "any recognized BIOS RAID sets. Ignoring disk %(unusedRaidMems)s.",
                   "Disks %(unusedRaidMems)s contain BIOS RAID metadata, but are not part of "
                   "any recognized BIOS RAID sets. Ignoring disks %(unusedRaidMems)s.",
                   len(unusedRaidMembers)) % {"unusedRaidMems": ", ".join(unusedRaidMembers)},
                custom_icon="warning")

    def resetInitializeDiskQuestion(self):
        self._initLabelAnswers = {}

    def questionInitializeDisk(self, path, description, size):

        retVal = False # The less destructive default

        if not path:
            return retVal

        # we are caching answers so that we don't
        # ask in each storage.reset() again
        if path in self._initLabelAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._initLabelAnswers[path])
            return self._initLabelAnswers[path]
        elif "all" in self._initLabelAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._initLabelAnswers["all"])
            return self._initLabelAnswers["all"]

        rc = self.reinitializeWindow(_("Storage Device Warning"),
                                     path, size, description)

        if rc == 0:
            retVal = False
        elif rc == 1:
            path = "all"
            retVal = False
        elif rc == 2:
            retVal = True
        elif rc == 3:
            path = "all"
            retVal = True

        self._initLabelAnswers[path] = retVal
        return retVal

    def resetReinitInconsistentLVMQuestion(self):
        self._inconsistentLVMAnswers = {}

    def questionReinitInconsistentLVM(self, pv_names=None, lv_name=None, vg_name=None):

        retVal = False # The less destructive default
        allSet = frozenset(["all"])

        if not pv_names or (lv_name is None and vg_name is None):
            return retVal

        # We are caching answers so that we don't ask for ignoring
        # in each storage.reset() again (note that reinitialization is
        # done right after confirmation in dialog, not as a planned
        # action).
        key = frozenset(pv_names)
        if key in self._inconsistentLVMAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._inconsistentLVMAnswers[key])
            return self._inconsistentLVMAnswers[key]
        elif allSet in self._inconsistentLVMAnswers:
            log.info("UI not asking about disk initialization, "
                     "using cached answer: %s" % self._inconsistentLVMAnswers[allSet])
            return self._inconsistentLVMAnswers[allSet]

        if vg_name is not None:
            message = "Volume Group %s" % vg_name
        elif lv_name is not None:
            message = "Logical Volume %s" % lv_name

        na = {'msg': message, 'pvs': ", ".join(pv_names)}
        rc = self.messageWindow(_("Warning"),
                  _("Error processing LVM.\n"
                    "There is inconsistent LVM data on %(msg)s.  You can "
                    "reinitialize all related PVs (%(pvs)s) which will erase "
                    "the LVM metadata, or ignore which will preserve the "
                    "contents.  This action may also be applied to all other "
                    "PVs with inconsistent metadata.") % na,
                type="custom",
                custom_buttons = [ _("_Ignore"),
                                   _("Ignore _all"),
                                   _("_Re-initialize"),
                                   _("Re-ini_tialize all") ],
                custom_icon="question")
        if rc == 0:
            retVal = False
        elif rc == 1:
            key = allSet
            retVal = False
        elif rc == 2:
            retVal = True
        elif rc == 3:
            key = allSet
            retVal = True

        self._inconsistentLVMAnswers[key] = retVal
        return retVal

    def questionInitializeDASD(self, c, devs):
        """Ask if unformatted DASD's should be formatted"""
        title = P_("Unformatted DASD Device Found",
                   "Unformatted DASD Devices Found", c)
        msg = P_("Format uninitialized DASD device?\n\n"
                 "There is %d uninitialized DASD device on this "
                 "system.  To continue installation, the device must "
                 "be formatted.  Formatting will remove any data on "
                 "this device.",
                 "Format uninitialized DASD devices?\n\n"
                 "There are %d uninitialized DASD devices on this "
                 "system.  To continue installation, the devices must "
                 "be formatted.  Formatting will remove any data on "
                 "these devices.", c) % c
        icon = "/usr/share/icons/gnome/32x32/status/dialog-error.png"
        buttons = [_("_Format"), _("_Ignore")]
        return self.detailedMessageWindow(title, msg, devs.strip(),
                                             type="custom",
                                             custom_icon=icon,
                                             custom_buttons=buttons,
                                             expanded=True)

    def unsupported_steps(self):
        """ List of steps this interface is unable to carry out. """
        return []
