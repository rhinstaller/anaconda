# Action summary dialog
#
# Copyright (C) 2013-2014  Red Hat, Inc.
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
from pyanaconda.modules.common.structures.storage import DeviceActionData
from pyanaconda.ui.gui import GUIObject

__all__ = ["ActionSummaryDialog"]


class ActionSummaryDialog(GUIObject):
    builderObjects = ["actionStore", "summaryDialog"]
    mainWidgetName = "summaryDialog"
    uiFile = "spokes/lib/summary.glade"

    def __init__(self, data, device_tree):
        super().__init__(data)
        self._device_tree = device_tree
        self._store = self.builder.get_object("actionStore")
        self._index = 1

        # Get actions of the given device tree.
        self._actions = DeviceActionData.from_structure_list(
            device_tree.GetActions()
        )

        # Add actions to the dialog.
        for action in self._actions:
            self._add_action(action)

    def _add_action(self, action: DeviceActionData):
        # Get the action description.
        if action.action_type in ["destroy", "resize"]:
            action_color = "red"
        else:
            action_color = "green"

        # ruff: noqa: UP032
        action_description = "<span foreground='{color}'>{action}</span>".format(
            color=action_color,
            action=action.action_description
        )

        # Get the action order.
        index = self._index
        self._index += 1

        # Create a new row in the action store.
        self._store.append([
            index,
            action_description,
            action.object_description,
            action.device_description,
            action.attrs.get("mount-point", ""),
            action.attrs.get("serial", "")
        ])

    @property
    def actions(self):
        """A list of scheduled actions."""
        return self._actions

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc
