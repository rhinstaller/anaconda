#
# dispatch.py: install/upgrade master flow control
#
# Copyright (C) 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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

import string
from types import *

import indexed_dict
import errors
from constants import *
from packages import writeKSConfiguration, turnOnFilesystems
from packages import doPostAction
from packages import copyAnacondaLogs
from packages import firstbootConfiguration
from packages import betaNagScreen
from packages import setupTimezone
from packages import setFileCons
from storage import storageInitialize
from storage import storageComplete
from storage.partitioning import doAutoPartition
from bootloader import writeBootloader
from flags import flags
from upgrade import upgradeMountFilesystems
from upgrade import restoreTime
from upgrade import upgradeMigrateFind
from upgrade import findRootParts, queryUpgradeContinue
from installmethod import doMethodComplete
from kickstart import doKickstart, runPostScripts
from sshd import doSshd
from rescue import doRescue

from backend import doPostSelection, doBackendSetup, doBasePackageSelect
from backend import doPreInstall, doPostInstall, doInstall
from backend import writeConfiguration

from packages import doReIPL

import logging
log = logging.getLogger("anaconda")

class Step(object):
    SCHED_UNSCHEDULED = 0
    SCHED_SCHEDULED = 1 # will execute if not explicitly skipped
    SCHED_SKIPPED = 2   # is never going to execute
    SCHED_REQUESTED = 3 # will execute and can not be skipped
    SCHED_DONE = 4      # done is a final state

    sched_state_machine = [
        # Table of allowed state changes, rows are the current state, columns
        # are what we want to transition into. False when such transition is not
        # allowed.
        # unsch sched  skip   req    done
        [True , True , True , True , True ], # unscheduled
        [False, True , True , True , True ], # scheduled
        [False, False, True , False, False], # skipped
        [False, False, False, True , True ], # requested
        [False, False, False, False, True ]] # done

    def __init__(self, name, target = None):
        """ Dispatcher step object.

            Target is a callable that performs the step (direct step). It
            accepts a sole argument: the anaconda object. If target is None,
            user interface object is told to handle the step (i.e. indirect
            step).
        """
        self.name = name
        self.target = target # None for dynamic target (e.g. gui view)
        self._sched = self.SCHED_UNSCHEDULED

    def _reschedule(self, to_sched):
        new_sched = self.sched_state_machine[self._sched][to_sched]
        if new_sched is False:
            raise errors.DispatchError(
                "Can not reschedule step '%s' from '%s' to '%s'" %
                (self.name,
                 self.namesched(self._sched),
                 self.namesched(to_sched)))
        self._sched = to_sched

    @property
    def direct(self):
        return self.target is not None

    def done(self):
        self._reschedule(self.SCHED_DONE)

    def request(self):
        self._reschedule(self.SCHED_REQUESTED)

    def namesched(self, sched):
        return {
            self.SCHED_UNSCHEDULED : "unscheduled",
            self.SCHED_SCHEDULED   : "scheduled",
            self.SCHED_SKIPPED     : "skipped",
            self.SCHED_REQUESTED   : "requested",
            self.SCHED_DONE        : "done"
            }[sched]

    @property
    def sched(self):
        return self._sched

    def schedule(self):
        self._reschedule(self.SCHED_SCHEDULED)

    def skip(self):
        self._reschedule(self.SCHED_SKIPPED)


class Dispatcher(object):

    def __init__(self, anaconda):
        self.anaconda = anaconda
        self.anaconda.dir = DISPATCH_FORWARD
        self.step = None # name of the current step
        # step dictionary mapping step names to step objects
        self.steps = indexed_dict.IndexedDict()
        # Note that not only a subset of the steps is executed for a particular
        # run, depending on the kind of installation, user selection, kickstart
        # commands, used installclass and used user interface.
        self._add_step("sshd", doSshd)
        self._add_step("rescue", doRescue)
        self._add_step("kickstart", doKickstart)
        self._add_step("language")
        self._add_step("keyboard")
        self._add_step("betanag", betaNagScreen)
        self._add_step("filtertype")
        self._add_step("filter")
        self._add_step("storageinit", storageInitialize)
        self._add_step("findrootparts", findRootParts)
        self._add_step("findinstall")
        self._add_step("network")
        self._add_step("timezone")
        self._add_step("accounts")
        self._add_step("setuptime", setupTimezone)
        self._add_step("parttype")
        self._add_step("cleardiskssel")
        self._add_step("autopartitionexecute", doAutoPartition)
        self._add_step("partition")
        self._add_step("upgrademount", upgradeMountFilesystems)
        self._add_step("restoretime", restoreTime)
        self._add_step("upgradecontinue", queryUpgradeContinue)
        self._add_step("upgrademigfind", upgradeMigrateFind)
        self._add_step("upgrademigratefs")
        self._add_step("storagedone", storageComplete)
        self._add_step("enablefilesystems", turnOnFilesystems)
        self._add_step("upgbootloader")
        self._add_step("bootloader")
        self._add_step("reposetup", doBackendSetup)
        self._add_step("tasksel")
        self._add_step("basepkgsel", doBasePackageSelect)
        self._add_step("group-selection")
        self._add_step("postselection", doPostSelection)
        self._add_step("install")
        self._add_step("preinstallconfig", doPreInstall)
        self._add_step("installpackages", doInstall)
        self._add_step("postinstallconfig", doPostInstall)
        self._add_step("writeconfig", writeConfiguration)
        self._add_step("firstboot", firstbootConfiguration)
        self._add_step("instbootloader", writeBootloader)
        self._add_step("reipl", doReIPL)
        self._add_step("writeksconfig", writeKSConfiguration)
        self._add_step("setfilecon", setFileCons)
        self._add_step("copylogs", copyAnacondaLogs)
        self._add_step("methodcomplete", doMethodComplete)
        self._add_step("postscripts", runPostScripts)
        self._add_step("dopostaction", doPostAction)
        self._add_step("complete")

    def _add_step(self, name, target = None):
        self.steps[name] = Step(name, target)

    def _advance_step(self):
        i = self._step_index()
        self.step = self.steps[i + 1].name

    def _step_index(self):
        return self.steps.index(self.step)

    @property
    def dir(self):
        return self.anaconda.dir

    @dir.setter
    def dir(self, dir):
        if dir not in [DISPATCH_BACK, DISPATCH_FORWARD, DISPATCH_DEFAULT]:
            raise RuntimeError("dispatch: wrong direction code")
        if dir in [DISPATCH_BACK, DISPATCH_FORWARD]:
            self.anaconda.dir = dir

    def done_steps(self, *steps):
        map(lambda s: self.steps[s].done(), steps)

    def go_back(self):
        """
        The caller should make sure can_go_back() is True before calling this
        method.
        """
        self.dir = DISPATCH_BACK
        self.dispatch()

    def go_forward(self):
        self.dir = DISPATCH_FORWARD
        self.dispatch()

    def can_go_back(self):
        # Begin with the step before this one. If all steps are skipped,
        # we can not go backwards from this one.
        i = self._step_index() - 1
        while i >= 0:
            sname = self.steps[i].name
            if not self.step_is_direct(sname) and self.step_enabled(sname):
                return True
            i -= 1
        return False

    def request_step(self, *steps):
        map(lambda s: self.steps[s].request(), steps)

    def run(self):
        self.anaconda.intf.run(self.anaconda)
        log.info("dispatch: finished.")

    def schedule_steps(self, *steps):
        map(lambda s: self.steps[s].schedule(), steps)

    def step_disabled(self, step):
        """ True if step is not yet scheduled to be run or will never be run
            (i.e. is skipped).
        """
        return not self.step_enabled(step)

    def step_enabled(self, step):
        """ True if step is scheduled to be run or have been run already. """
        return self.steps[step].sched in [Step.SCHED_SCHEDULED,
                                          Step.SCHED_REQUESTED,
                                          Step.SCHED_DONE]

    def skipStep(self, *steps):
        map(lambda s: self.steps[s].skip(), steps)

    def step_is_direct(self, step):
        return self.steps[step].direct

    def dispatch(self):
        total_steps = len(self.steps)
        if self.step == None:
            log.info("dispatch: resetting to the first step.")
            self.step = self.steps[0].name
        else:
            log.info("dispatch: leaving (%d) step %s" %
                     (self.dir, self.step))
            self.done_steps(self.step)
            self._advance_step()

        while True:
            if self._step_index() >= total_steps:
                # installation has proceeded beyond the last step: finished
                self.anaconda.intf.shutdown()
                return
            if self.step_disabled(self.step):
                self._advance_step()
                continue
            log.info("dispatch: moving (%d) to step %s" %
                     (self.dir, self.step))
            if self.step_is_direct(self.step):
                # handle a direct step by just calling the function
                log.debug("dispatch: %s is a direct step" % self.step)
                self.dir = self.steps[self.step].target(self.anaconda)
            else:
                # handle an indirect step (IOW the user interface has a screen
                # to display to the user):
                rc = self.anaconda.intf.display_step(self.step)
                if rc == DISPATCH_WAITING:
                    # a new screen has been set up and we are waiting for the
                    # user input now (this only ever happens with the GTK UI and
                    # is because we need to get back to gtk.main())
                    return
                elif rc == DISPATCH_DEFAULT:
                    log.debug("dispatch: the interface chose "
                              "not to display step %s." % self.step)
                else:
                    self.dir = rc
            log.info("dispatch: leaving (%d) step %s" %
                     (self.dir, self.step))
            self.done_steps(self.step)
            self._advance_step()
