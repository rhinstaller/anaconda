#
# startup.py - code used during early startup with minimal dependencies
#
# Copyright (C) 2014  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#
import imp


def module_exists(module_path):
    """Report is a given module exists in the current module import pth or not.
    Supports checking bot modules ("foo") os submodules ("foo.bar.baz")

    :param str module_path: (sub)module identifier

    :returns: True if (sub)module exists in path, False if not
    :rtype: bool
    """

    module_path_components = module_path.split(".")
    module_name = module_path_components.pop()
    parent_module_path = None
    if module_path_components:
        # the path specifies a submodule ("bar.foo")
        # we need to chain-import all the modules in the submodule path before
        # we can check if the submodule itself exists
        for name in module_path_components:
            module_info = imp.find_module(name, parent_module_path)
            module = imp.load_module(name, *module_info)
            if module:
                parent_module_path = module.__path__
            else:
                # one of the parents was not found, abort search
                return False
    # if we got this far we should have either some path or the module is
    # not a submodule and the default set of paths will be used (path=None)
    try:
        # if the module is not found imp raises an ImportError
        imp.find_module(module_name, parent_module_path)
        return True
    except ImportError:
        return False


def get_anaconda_version_string():
    """Return a string describing current Anaconda version.
    If the current version can't be determined the string
    "unknown" will be returned.

    :returns: string describing Anaconda version
    :rtype: str
    """

    # we are importing the version module directly so that we don't drag in any
    # non-necessary stuff; we also need to handle the possibility of the
    # import itself failing
    if module_exists("pyanaconda.version"):
        # Ignore pylint not finding the version module, since thanks to automake
        # there's a good chance that version.py is not in the same directory as
        # the rest of pyanaconda.
        from pyanaconda import version # pylint: disable=no-name-in-module
        return version.__version__
    else:
        return "unknown"

