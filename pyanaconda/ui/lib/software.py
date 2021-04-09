#
# Copyright (C) 2021  Red Hat, Inc.
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

log = get_module_logger(__name__)


def is_software_selection_complete(dnf_manager, selection, kickstarted=False):
    """Check the completeness of the software selection.

    :param dnf_manager: a DNF manager
    :param selection: a packages selection data
    :param kickstarted: is the selection configured by a kickstart file?
    :return: True if the selection is complete, otherwise False
    """
    # The environment doesn't have to be set for the automated installation.
    if kickstarted and not selection.environment:
        return True

    # The selected environment has to be valid.
    return dnf_manager.is_environment_valid(selection.environment)


def get_software_selection_status(dnf_manager, selection, kickstarted=False):
    """Get the software selection status.

    :param dnf_manager: a DNF manager
    :param selection: a packages selection data
    :param kickstarted: is the selection configured by a kickstart file?
    :return: a translated string with the selection status
    """
    if kickstarted:
        # The %packages section is present in kickstart, but environment is not set.
        if not selection.environment:
            return _("Custom software selected")
        # The environment is set to an invalid value.
        elif not dnf_manager.is_environment_valid(selection.environment):
            return _("Invalid environment specified in kickstart")
    else:
        if not selection.environment:
            # No environment is set.
            return _("Please confirm software selection")
        elif not dnf_manager.is_environment_valid(selection.environment):
            # Selected environment is not valid, this can happen when a valid environment
            # is selected (by default, manually or from kickstart) and then the installation
            # source is switched to one where the selected environment is no longer valid.
            return _("Selected environment is not valid")

    # The valid environment is set.
    environment_data = dnf_manager.get_environment_data(selection.environment)
    return environment_data.name
