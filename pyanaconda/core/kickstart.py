#
# Base kickstart objects for Anaconda modules.
#
# Copyright (C) 2017 Red Hat, Inc.
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
from pykickstart.base import BaseHandler
from pykickstart.parser import KickstartParser
from pykickstart.version import DEVEL

__all__ = ["KickstartSpecification", "NoKickstartSpecification",
           "get_kickstart_handler", "get_kickstart_parser"]


class KickstartSpecification(object):
    """Specification of kickstart data.

    This specification can be used to get the corresponding
    handler and parser to parse and handle kickstart data
    described by this specification.

    You should call get_kickstart_handler to get the kickstart
    handler for this specification.

    You should call get_kickstart_parser to get the kickstart
    parser for this specification.

    A specification is defined by these attributes:

    version     - version of a kickstart data
    commands    - mapping of kickstart command names to
                  classes that represent them
    data        - mapping of kickstart data names to
                  classes that represent them
    sections    - mapping of kickstart sections names to
                  classes that represent them
    """

    version = DEVEL
    commands = {}
    data = {}
    sections = {}


class NoKickstartSpecification(KickstartSpecification):
    """Specification for no kickstart data."""
    pass


class KickstartSpecificationHandler(BaseHandler):
    """Handler defined by a kickstart specification.

    You should call get_kickstart_handler to get a handler.
    """

    def __init__(self, *args, version=DEVEL, **kwargs):
        self.version = version
        super().__init__(*args, **kwargs)


class KickstartSpecificationParser(KickstartParser):
    """Parser defined by a kickstart specification.

    You should call get_kickstart_parser to get a parser.
    """

    def setupSection(self):
        """Do not setup any sections by default."""
        pass


def get_kickstart_handler(specification):
    """Return a kickstart handler.

    :param specification: a kickstart specification
    :return: a kickstart handler
    """
    return KickstartSpecificationHandler(specification.commands,
                                         specification.data,
                                         specification.version)


def get_kickstart_parser(handler, specification):
    """Return a kickstart parser.

    :param handler: a kickstart handler
    :param specification: a kickstart specification
    :return: a kickstart parser
    """
    parser = KickstartSpecificationParser(handler)

    for section in specification.sections.values():
        parser.registerSection(section(handler))

    return parser
