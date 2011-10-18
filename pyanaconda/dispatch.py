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
        [True,  True , True , True , True ], # scheduled
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
        self._changes = {} # tracks changes (FROM, TO) in scheduling of other steps
        self.name = name
        self.target = target # None for dynamic target (e.g. gui view)
        self._sched = self.SCHED_UNSCHEDULED
        self.client_data = {} # used by the client code, not reset when
                              # scheduling is reverted

    def _reschedule(self, to_sched, current_step):
        s_from = self.sched
        new_sched = self.sched_state_machine[self.sched][to_sched]
        if new_sched is False:
            raise errors.DispatchError(
                "Can not reschedule step '%s' from '%s' to '%s'" %
                (self.name,
                 self.namesched(self._sched),
                 self.namesched(to_sched)))
        self._sched = to_sched
        # only track scheduling if we are in a step and if something changes:
        if current_step and s_from != self._sched:
            current_step.record_history(self, s_from, self.sched)

    @property
    def changes(self):
        return self._changes

    def clear_changes(self):
        self._changes = {}

    @property
    def direct(self):
        return self.target is not None

    def done(self, current_step):
        return self._reschedule(self.SCHED_DONE, current_step)

    def request(self, current_step):
        return self._reschedule(self.SCHED_REQUESTED, current_step)

    def unschedule(self, current_step):
        return self._reschedule(self.SCHED_UNSCHEDULED, current_step)

    def namesched(self, sched):
        return {
            self.SCHED_UNSCHEDULED : "unscheduled",
            self.SCHED_SCHEDULED   : "scheduled",
            self.SCHED_SKIPPED     : "skipped",
            self.SCHED_REQUESTED   : "requested",
            self.SCHED_DONE        : "done"
            }[sched]

    def record_history(self, step, s_from, s_to):
        """ Stores information about scheduling changes into self.

            step is a step where scheduling changed from s_from to s_to. the
            self object in this method should be the currently executing object.
        """
        if step.name in self._changes:
            s_from = self._changes[step.name][0]
        self._changes[step.name] = (s_from, s_to)

    def revert_sched(self, s_from, s_to):
        assert(self.sched == s_to)
        self._sched = s_from

    @property
    def sched(self):
        return self._sched

    def schedule(self, current_step):
        return self._reschedule(self.SCHED_SCHEDULED, current_step)

    def skip(self, current_step):
        return self._reschedule(self.SCHED_SKIPPED, current_step)

class Dispatcher(object):

    def __init__(self, anaconda):
        self.anaconda = anaconda
        self.anaconda.dir = DISPATCH_FORWARD
        self.step = None # name of the current step
        self.stop = False
        # step dictionary mapping step names to step objects
        self.steps = indexed_dict.IndexedDict()
        self.init_steps()

    def _advance_step(self):
        if self.step is None:
            # initialization
            log.info("dispatch: resetting to the first step.")
            self.step = self.steps[0].name
        elif self._step_index() < len(self.steps) - 1:
            i = self._step_index()
            if self.dir == DISPATCH_BACK:
                # revert whatever changed in the current step
                self._revert_scheduling(self.step)
            self.step = self.steps[i + self.dir].name
            if self.dir == DISPATCH_BACK:
                # revert whatever changed in the step we moved back to
                self._revert_scheduling(self.step)
        else:
            # advancing from the last step
            self.step = "_invalid_"
            self.stop = True

    def _current_step(self):
        if self.step:
            return self.steps[self.step]
        return None

    def _revert_scheduling(self, reverted_step):
        """ Revert scheduling changes that happened during reverted_step. """
        for (step, (s_from, s_to)) in self.steps[reverted_step].changes.items():
            self.steps[step].revert_sched(s_from, s_to)
        self.steps[reverted_step].clear_changes()

    def _step_index(self):
        return self.steps.index(self.step)

    def add_step(self, name, target = None):
        self.steps[name] = Step(name, target)

    def can_go_back(self):
        # Begin with the step before this one. If all steps are skipped,
        # we can not go backwards from this one.
        if self.step == None:
            return False
        i = self._step_index() - 1
        while i >= 0:
            sname = self.steps[i].name
            if not self.step_is_direct(sname) and self.step_enabled(sname):
                return True
            i -= 1
        return False

    #pylint: disable-msg=E0202
    @property
    def dir(self):
        return self.anaconda.dir

    # pylint: disable-msg=E0102,E0202,E1101
    @dir.setter
    def dir(self, dir):
        if dir not in [DISPATCH_BACK, DISPATCH_FORWARD, DISPATCH_DEFAULT]:
            raise RuntimeError("dispatch: wrong direction code")
        if dir in [DISPATCH_BACK, DISPATCH_FORWARD]:
            self.anaconda.dir = dir

    def done_steps(self, *steps):
        changes = map(lambda s: self.steps[s].done(self._current_step()), steps)

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

    def init_steps(self):
        # Note that not only a subset of the steps is executed for a particular
        # run, depending on the kind of installation, user selection, kickstart
        # commands, used installclass and used user interface.
        self.add_step("sshd", doSshd)
        self.add_step("rescue", doRescue)
        self.add_step("kickstart", doKickstart)
        self.add_step("language")
        self.add_step("keyboard")
        self.add_step("betanag", betaNagScreen)
        self.add_step("filtertype")
        self.add_step("filter")
        self.add_step("storageinit", storageInitialize)
        self.add_step("findrootparts", findRootParts)
        self.add_step("findinstall")
        self.add_step("network")
        self.add_step("timezone")
        self.add_step("accounts")
        self.add_step("setuptime", setupTimezone)
        self.add_step("parttype")
        self.add_step("cleardiskssel")
        self.add_step("autopartitionexecute", doAutoPartition)
        self.add_step("partition")
        self.add_step("upgrademount", upgradeMountFilesystems)
        self.add_step("restoretime", restoreTime)
        self.add_step("upgradecontinue", queryUpgradeContinue)
        self.add_step("upgrademigfind", upgradeMigrateFind)
        self.add_step("upgrademigratefs")
        self.add_step("storagedone", storageComplete)
        self.add_step("enablefilesystems", turnOnFilesystems)
        self.add_step("upgbootloader")
        self.add_step("bootloader")
        self.add_step("reposetup", doBackendSetup)
        self.add_step("tasksel")
        self.add_step("basepkgsel", doBasePackageSelect)
        self.add_step("group-selection")
        self.add_step("postselection", doPostSelection)
        self.add_step("install")
        self.add_step("preinstallconfig", doPreInstall)
        self.add_step("installpackages", doInstall)
        self.add_step("postinstallconfig", doPostInstall)
        self.add_step("writeconfig", writeConfiguration)
        self.add_step("firstboot", firstbootConfiguration)
        self.add_step("instbootloader", writeBootloader)
        self.add_step("reipl", doReIPL)
        self.add_step("writeksconfig", writeKSConfiguration)
        self.add_step("setfilecon", setFileCons)
        self.add_step("copylogs", copyAnacondaLogs)
        self.add_step("methodcomplete", doMethodComplete)
        self.add_step("postscripts", runPostScripts)
        self.add_step("dopostaction", doPostAction)
        self.add_step("complete")

    def request_steps(self, *steps):
        changes = map(lambda s: self.steps[s].request(self._current_step()), steps)

    def request_steps_gently(self, *steps):
        """ Requests steps and won't raise an error if it is not possible for
            some of them.
        """
        for step in steps:
            try:
                self.request_steps(step)
            except errors.DispatchError as e:
                log.debug("dispatch: %s" % e)

    def reset_scheduling(self):
        log.info("dispatch: resetting scheduling")
        for step in self.steps:
            try:
                self.steps[step].unschedule(self._current_step())
            except errors.DispatchError as e:
                log.debug("dispatch: %s" % e)
        log.info("dispatch: resetting finished.")

    def run(self):
        self.anaconda.intf.run(self.anaconda)
        log.info("dispatch: finished.")

    def schedule_steps(self, *steps):
        changes = map(lambda s: self.steps[s].schedule(self._current_step()), steps)

    def schedule_steps_gently(self, *steps):
        """ Schedules steps and won't raise an error if it is not possible for
            some of them.
        """
        for step in steps:
            try:
                self.schedule_steps(step)
            except errors.DispatchError as e:
                log.debug("dispatch: %s" % e)

    def step_data(self, step):
        return self.steps[step].client_data

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

    def skip_steps(self, *steps):
        changes = map(lambda s: self.steps[s].skip(self._current_step()), steps)

    def step_is_direct(self, step):
        return self.steps[step].direct

    def dispatch(self):
        if self.step:
            log.info("dispatch: leaving (%d) step %s" %
                     (self.dir, self.step))
            self.done_steps(self.step)
        self._advance_step()

        while True:
            if self.stop:
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
