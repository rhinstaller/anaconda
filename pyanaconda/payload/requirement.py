#
# Copyright (C) 2019  Red Hat, Inc.
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

from collections import OrderedDict, namedtuple
from pyanaconda.core.constants import PayloadRequirementType
from pyanaconda.payload.errors import PayloadRequirementsMissingApply

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)

PayloadRequirementReason = namedtuple('PayloadRequirementReason', ['reason', 'strong'])


__all__ = ["PayloadRequirements", "PayloadRequirement"]


class PayloadRequirement(object):
    """An object to store a payload requirement with info about its reasons.

    For each requirement multiple reasons together with their strength
    can be stored in this object using the add_reason method.
    A reason should be just a string with description (ie for tracking purposes).
    Strength is a boolean flag that can be used to indicate whether missing the
    requirement should be considered fatal. Strength of the requirement is
    given by strength of all its reasons.
    """
    def __init__(self, req_id, reasons=None):
        self._id = req_id
        self._reasons = reasons or []

    @property
    def id(self):
        """Identifier of the requirement (eg a package name)"""
        return self._id

    @property
    def reasons(self):
        """List of reasons for the requirement"""
        return [reason for reason, strong in self._reasons]

    @property
    def strong(self):
        """Strength of the requirement (ie should it be considered fatal?)"""
        return any(strong for reason, strong in self._reasons)

    def add_reason(self, reason, strong=False):
        """Adds a reason to the requirement with optional strength of the reason"""
        self._reasons.append(PayloadRequirementReason(reason, strong))

    def __str__(self):
        return "PayloadRequirement(id=%s, reasons=%s, strong=%s)" % (self.id,
                                                                     self.reasons,
                                                                     self.strong)

    def __repr__(self):
        return 'PayloadRequirement(id=%s, reasons=%s)' % (self.id, self._reasons)


class PayloadRequirements(object):
    """A container for payload requirements imposed by installed functionality.

    Stores names of packages and groups required by used installer features,
    together with descriptions of reasons why the object is required and if the
    requirement is strong. Not satisfying strong requirement would be fatal for
    installation.
    """

    def __init__(self):
        self._apply_called_for_all_requirements = True
        self._apply_cb = None
        self._reqs = {}
        for req_type in PayloadRequirementType:
            self._reqs[req_type] = OrderedDict()

    def add_packages(self, package_names, reason, strong=True):
        """Add packages required for the reason.

        If a package is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param package_names: names of packages to be added
        :type package_names: list of str
        :param reason: description of reason for adding the packages
        :type reason: str
        :param strong: is the requirement strong (ie is not satisfying it fatal?)
        :type strong: bool
        """
        self._add(PayloadRequirementType.package, package_names, reason, strong)

    def add_groups(self, group_ids, reason, strong=True):
        """Add groups required for the reason.

        If a group is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param group_ids: ids of groups to be added
        :type group_ids: list of str
        :param reason: descripiton of reason for adding the groups
        :type reason: str
        :param strong: is the requirement strong
        :type strong: bool
        """
        self._add(PayloadRequirementType.group, group_ids, reason, strong)

    def add_requirements(self, requirements):
        """Add requirements from a list of Requirement instances.

        :param requirements: list of Requirement instances
        """
        for requirement in requirements:
            # check requirement type and add a payload requirement appropriately
            if requirement.type == "package":
                self.add_packages([requirement.name], reason=requirement.reason)
            elif requirement.type == "group":
                self.add_groups([requirement.name], reason=requirement.reason)
            else:
                log.warning("Unknown type: %s in requirement: %s, skipping.", requirement.type, requirement)

    def _add(self, req_type, ids, reason, strong):
        if not ids:
            log.debug("no %s requirement added for %s", req_type.value, reason)
        reqs = self._reqs[req_type]
        for r_id in ids:
            if r_id not in reqs:
                reqs[r_id] = PayloadRequirement(r_id)
            reqs[r_id].add_reason(reason, strong)
            self._apply_called_for_all_requirements = False
            log.debug("added %s requirement '%s' for %s, strong=%s",
                      req_type.value, r_id, reason, strong)

    @property
    def packages(self):
        """List of package requirements.

        return: list of package requirements
        rtype: list of PayloadRequirement
        """
        return list(self._reqs[PayloadRequirementType.package].values())

    @property
    def groups(self):
        """List of group requirements.

        return: list of group requirements
        rtype: list of PayloadRequirement
        """
        return list(self._reqs[PayloadRequirementType.group].values())

    def set_apply_callback(self, callback):
        """Set the callback for applying requirements.

        The callback will be called by apply() method.
        param callback: callback function to be called by apply() method
        type callback: a function taking one argument (requirements object)
        """
        self._apply_cb = callback

    def apply(self):
        """Apply requirements using callback function.

        Calls the callback supplied via set_apply_callback() method. If no
        callback was set, an axception is raised.

        return: return value of the callback
        rtype: type of the callback return value
        raise PayloadRequirementsMissingApply: if there is no callback set

        """
        if self._apply_cb:
            self._apply_called_for_all_requirements = True
            rv = self._apply_cb(self)
            log.debug("apply with result %s called on requirements %s", rv, self)
            return rv
        else:
            raise PayloadRequirementsMissingApply

    @property
    def applied(self):
        """Was all requirements applied?

        return: Was apply called for all current requirements?
        rtype: bool
        """
        return self.empty or self._apply_called_for_all_requirements

    @property
    def empty(self):
        """Are requirements empty?

        return: True if there are no requirements, else False
        rtype: bool
        """
        return not any(self._reqs.values())

    def __str__(self):
        r = []
        for req_type in PayloadRequirementType:
            for rid, req in self._reqs[req_type].items():
                r.append((req_type.value, rid, req))
        return str(r)
