# The configuration of the installation.
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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#


class Configuration(object):
    """The class that holds the installation configuration."""

    def __init__(self, data, storage, payload, instclass):
        """Create a new configuration instance.

        :param data: installation settings
        :type data: an instance of a pykickstart Handler object

        :param storage: a storage devices configuration
        :type storage: an instance of storage.Storage

        :param payload: a software configuration
        :type payload: an instance of a packaging.Payload subclass

        :param instclass: distribution-specific installation information
        :type instclass: an instance of a BaseInstallClass subclass
        """
        self.data = data
        self.storage = storage
        self.payload = payload
        self.instclass = instclass
