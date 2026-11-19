#
# Collect completeness of the modules.
#
# Copyright (C) 2026 Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _
from pyanaconda.modules.common.structures.completeness import (
    IncompletenessReason,
    ModuleCompleteness,
)

log = get_module_logger(__name__)

__all__ = ["CompletenessManager"]


class CompletenessManager:
    """Manager of the completeness of the modules.

    Fans out to the modules, collects what they report and applies one
    domain-free rule: every mandatory module has to be complete. It holds
    no knowledge about any individual module, so addons participate
    without changes here.
    """

    def __init__(self):
        self._module_observers = []

    def on_module_observers_changed(self, observers):
        """Set module observers which will be asked about completeness."""
        self._module_observers = list(observers)

    def collect_completeness(self):
        """Collect the completeness of the modules.

        Modules that are not running are left out entirely. An optional
        module that is absent cannot block an installation.

        :return: a list of ModuleCompleteness
        """
        reports = []

        for observer in self._module_observers:
            if not observer.is_service_available:
                log.debug(
                    "Module %s is not available, excluding it from completeness.",
                    observer.service_name
                )
                continue

            reports.append(self._collect_from_module(observer))

        return reports

    def _collect_from_module(self, observer):
        """Ask a single module about its completeness.

        A module that cannot answer is reported as incomplete with an
        invalid reason rather than being skipped. Failing closed keeps a
        broken addon from silently becoming a green light, and naming it
        in a reason gives the user something to act on.

        :param observer: a module observer
        :return: a ModuleCompleteness
        """
        report = ModuleCompleteness()
        report.service_name = observer.service_name

        # FIXME: A module that never answers blocks this call for as long as
        # the bus allows. Phase 0 only fails closed on modules that answer
        # with an error. Choosing a call timeout is an open question in the
        # design document.
        try:
            proxy = observer.proxy
            report.complete = proxy.Complete
            report.mandatory = proxy.Mandatory
            report.reasons = IncompletenessReason.from_structure_list(
                proxy.Incompleteness
            )
        except Exception as e:  # pylint: disable=broad-except
            log.warning(
                "Module %s failed to report its completeness: %s",
                observer.service_name, e
            )
            report.complete = False
            report.mandatory = True
            report.reasons = [
                IncompletenessReason.for_invalid(
                    "boss.module-unresponsive",
                    _("The {} module failed to report its status.").format(
                        observer.service_name
                    ),
                )
            ]

        log.debug(
            "Module %s is complete=%s mandatory=%s with reasons: %s",
            report.service_name, report.complete, report.mandatory, report.reasons
        )
        return report

    def is_ready_to_install(self):
        """Is every mandatory module complete?

        Only meaningful once nothing anywhere is busy. While a busy reason
        exists, a False answer means "ask again", not "cannot install".

        :return: True if no mandatory module blocks the installation
        """
        return all(
            report.complete
            for report in self.collect_completeness()
            if report.mandatory
        )

    def collect_blocking_reasons(self):
        """Collect the reasons that block the installation.

        Reasons from modules that are not mandatory are left out: they
        explain an incompleteness that nobody has to resolve.

        :return: a list of IncompletenessReason annotated with their module
        """
        reasons = []

        for report in self.collect_completeness():
            if report.complete or not report.mandatory:
                continue

            for reason in report.reasons:
                reason.module_name = report.service_name
                reasons.append(reason)

        return reasons
