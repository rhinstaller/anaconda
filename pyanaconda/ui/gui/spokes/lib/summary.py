# Action summary dialog
#
# Copyright (C) 2013  Red Hat, Inc.
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

from pyanaconda.ui.gui import GUIObject

from blivet.deviceaction import ACTION_TYPE_DESTROY, ACTION_TYPE_RESIZE, ACTION_OBJECT_FORMAT

__all__ = ["ActionSummaryDialog"]

class ActionSummaryDialog(GUIObject):
    builderObjects = ["actionStore", "summaryDialog"]
    mainWidgetName = "summaryDialog"
    uiFile = "spokes/lib/summary.glade"

    def __init__(self, data):
        GUIObject.__init__(self, data)
        self._store = self.builder.get_object("actionStore")

    # pylint: disable-msg=W0221
    def initialize(self, actions):
        for (i, action) in enumerate(actions, start=1):
            mountpoint = ""

            if action.type in [ACTION_TYPE_DESTROY, ACTION_TYPE_RESIZE]:
                typeString = """<span foreground='red'>%s</span>""" % action.typeDesc.title()
            else:
                typeString = """<span foreground='green'>%s</span>""" % action.typeDesc.title()
                if action.obj == ACTION_OBJECT_FORMAT:
                    mountpoint = getattr(action.device.format, "mountpoint", "")

            self._store.append([i,
                                typeString,
                                action.objectTypeString,
                                action.device.name,
                                mountpoint])

    # pylint: disable-msg=W0221
    def refresh(self, actions):
        GUIObject.refresh(self)

        self._store.clear()
        self.initialize(actions)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc
