#
# Module for Payload requirements.
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
from collections import OrderedDict

from pyanaconda.core.constants import PayloadRequirementType
from pyanaconda.dbus import DBus
from pyanaconda.modules.common.base import BaseModule
from pyanaconda.modules.common.constants.objects import REQUIREMENTS
from pyanaconda.modules.common.structures.payload import Requirement
from pyanaconda.modules.payload.requirements_interface import RequirementsInterface


from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class RequirementsModule(BaseModule):
    """The payload requirements module.

    Stores names of packages and groups required by used installer features,
    together with descriptions of reasons why the object is required and if the
    requirement is strong. Not satisfying strong requirement would be fatal for
    installation.
    """

    def __init__(self):
        super().__init__()
        self._reqs = {}
        for req_type in PayloadRequirementType:
            self._reqs[req_type] = OrderedDict()

    def publish(self):
        """Publish the module."""
        DBus.publish_object(REQUIREMENTS.object_path, RequirementsInterface(self))

    def add_packages(self, package_ids, reason, strong=True):
        """Add packages required for the reason.

        If a package is already required, the new reason will be
        added and the strength of the requirement will be updated.

        :param package_ids: names of packages to be added
        :type package_ids: list of str
        :param reason: description of reason for adding the packages
        :type reason: str
        :param strong: is the requirement strong (ie is not satisfying it fatal?)
        :type strong: bool
        """
        self._add(PayloadRequirementType.package, package_ids, reason, strong)

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

    def _add(self, req_type, ids, reason, strong):
        if not ids:
            log.debug("no %s requirement added for %s", req_type.value, reason)

        reqs = self._reqs[req_type]

        for r_id in ids:
            if r_id not in reqs:
                req = Requirement()
                req.id = r_id
                reqs[r_id] = req
            reqs[r_id].add_reason(reason, strong)
            log.debug("added %s requirement '%s' for '%s', strong=%s",
                      req_type.value, r_id, reason, strong)

    @property
    def packages(self):
        """List of package requirements.

        return: list of package requirements
        rtype: list of Requirement
        """
        return list(self._reqs[PayloadRequirementType.package].values())

    @property
    def groups(self):
        """List of group requirements.

        return: list of group requirements
        rtype: list of Requirement
        """
        return list(self._reqs[PayloadRequirementType.group].values())

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
