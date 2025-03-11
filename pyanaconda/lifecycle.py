# controller.py
# Anaconda module lifecycle controller.
#
# Copyright (C) 2016  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from threading import RLock

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.signal import Signal
from pyanaconda.core.util import synchronized

log = get_module_logger(__name__)

_controllers = {}
_controller_categories_map = {}


def get_controller_by_category(category_name):
    """Return the controller instance that "owns" the corresponding category.

    This is more or less a workaround to the fact that spokes
    need to know what's their controller, but the controllers
    are indexed by hub name and spokes don't have a direct reference
    to the hub they are displayed on.

    Spokes know their category and hubs know what categories the and
    categories  should not be on two hubs. So we match the spoke category
    to get the controller corresponding to the spoke.

    :param str category_name: a spoke category name
    :returns: a Controller instance "owning" the category or None if no matching instance is found
    :rtype: str or None

    """
    for controller_name, controller_categories in _controller_categories_map.items():
        if category_name in controller_categories:
            return _controllers[controller_name]
    # no controller has been found for the given spoke based on it's category
    return None


def get_controller_by_name(controller_name):
    """Return controller instance by name.

    This function wraps the internal controller dictionary, so that it is not directly exposed.

    The controller names currently correspond to hub class name, eq.:
    SummaryHub, ProgressHub, etc.

    :param str controller_name: a name of a controller name
    """
    return _controllers.get(controller_name)


def add_controller(controller_name, controller_categories):
    # The controller name is currently based on Hub name
    # and None indicates that the Hub subclass has not
    # set the hub_name property to a non-default value.
    if controller_name is None:
        log.warning("Controller name is None.")
    else:
        log.info("Adding controller: %s", controller_name)
    controller = Controller()
    _controllers[controller_name] = controller
    _controller_categories_map[controller_name] = controller_categories
    return controller


class Controller:
    """A singleton that track initialization of Anaconda modules."""
    def __init__(self):
        self._lock = RLock()
        self._modules = set()
        self._all_modules_added = False
        self.init_done = Signal()
        self._init_done_triggered = False
        self._added_module_count = 0

    @synchronized
    def module_init_start(self, module):
        """Tell the controller that a module has started initialization.

        :param module: a module which has started initialization
        """
        if self._all_modules_added:
            log.warning("Late module_init_start() from: %s", self)
        elif module in self._modules:
            log.warning("Module already marked as initializing: %s", module)
        else:
            self._added_module_count += 1
            self._modules.add(module)

    def all_modules_added(self):
        """Tell the controller that all expected modules have started initialization.

        Tell the controller that all expected modules have been registered
        for initialization tracking (or have already been initialized)
        and no more are expected to be added.

        This is needed so that we don't prematurely trigger the init_done signal
        when all known modules finish initialization while other modules have not
        yet been added.
        """
        init_done = False
        with self._lock:
            log.info("Initialization of all modules (%d) has been started.", self._added_module_count)
            self._all_modules_added = True

            # if all modules finished initialization before this was added then
            # trigger the init_done signal at once
            if not self._modules and not self._init_done_triggered:
                self._init_done_triggered = True
                init_done = True

        # we should emit the signal out of the main lock as it doesn't make sense
        # to hold the controller-state lock once we decide to the trigger init_done signal
        # (and any callbacks registered on it)
        if init_done:
            self._trigger_init_done()

    def module_init_done(self, module):
        """Tell the controller that a module has finished initialization.

        And if no more modules are being initialized trigger the init_done signal.

        :param module: a module that has finished initialization
        """
        init_done = False
        with self._lock:
            # prevent the init_done signal from
            # being triggered more than once
            if self._init_done_triggered:
                log.warning("Late module_init_done from module %s.", module)
            else:
                if module in self._modules:
                    log.info("Module initialized: %s", module)
                    self._modules.discard(module)
                else:
                    log.warning("Unknown module reported as initialized: %s", module)
                # don't trigger the signal if all modules have not yet been added
                if self._all_modules_added and not self._modules:
                    init_done = True
                    self._init_done_triggered = True

        # we should emit the signal out of the main lock as it doesn't make sense
        # to hold the controller-state lock once we decide to the trigger init_done signal
        # (and any callbacks registered on it)
        if init_done:
            self._trigger_init_done()

    def _trigger_init_done(self):
        log.info("All modules have been initialized.")
        self.init_done.emit()
