#
# Kickstart specification for baz.
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
from pykickstart.options import KSOptionParser

from pyanaconda.core.kickstart import VERSION, KickstartSpecification
from pyanaconda.core.kickstart.addon import AddonData


class BazData(AddonData):
    """The kickstart data for baz."""

    def __init__(self):
        super().__init__()
        self.seen = False
        self.foo = None
        self.bar = False
        self.lines = []

    def handle_header(self, args, line_number=None):
        # Create the argument parser.
        op = KSOptionParser(
            prog="%addon my_example_baz",
            version=VERSION,
            description="My addon baz."
        )

        op.add_argument(
            "--foo",
            type=int,
            default=None,
            version=VERSION,
            help="Specify foo."
        )

        op.add_argument(
            "--bar",
            action="store_true",
            default=False,
            version=VERSION,
            help="Specify bar."
        )

        # Parse the arguments.
        ns = op.parse_args(args=args, lineno=line_number)

        # Store the result of the parsing.
        self.seen = True
        self.foo = ns.foo
        self.bar = ns.bar

    def handle_line(self, line, line_number=None):
        self.lines.append(line.strip())

    def __str__(self):
        if not self.seen:
            return ""

        section = "\n%addon my_example_baz"

        if self.foo is not None:
            section += " --foo={}".format(self.foo)

        if self.bar:
            section += " --bar"

        for line in self.lines:
            section += "\n" + line

        section += "\n%end\n"
        return section


class BazKickstartSpecification(KickstartSpecification):

    version = VERSION

    addons = {
        "my_example_baz": BazData
    }
