# Base classes for all user interfaces.
#
# Copyright (C) 2011  Red Hat, Inc.
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

class UserInterface(object):
    """This is the base class for all kinds of install UIs.  It primarily
       defines what kinds of dialogs and entry widgets every interface must
       provide that the rest of anaconda may rely upon.
    """
    def __init__(self):
        """Create a new UserInterface instance."""
        if self.__class__ is UserInterface:
            raise TypeError("UserInterface is an abstract class.")

    def setup(self, data):
        """Construct all the objects required to implement this interface.
           This method must be provided by all subclasses.
        """
        raise NotImplementedError

    def run(self):
        """Run the interface.  This should do little more than just pass
           through to something else's run method, but is provided here in
           case more is needed.  This method must be provided by all subclasses.
        """
        raise NotImplementedError
