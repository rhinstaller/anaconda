# Framework for testing translatable strings
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>

"""
Framework for running tests against translatable strings.

Tests are loaded from modules in this directory. A test is any callable object
within the module with a name that starts with 'test_'.

Each test is called with a POEntry object as an argument. A test passes if it
returns without raising an exception.
"""

try:
    import polib
except ImportError:
    print("You need to install the python-polib package to read translations")
    raise

# Gather tests from this directory
import pkgutil
_tests = []
for finder, mod_name, _ispkg in pkgutil.iter_modules(__path__):
    # Skip __main__
    if mod_name == "__main__":
        continue

    # Load the module
    module = finder.find_module(mod_name).load_module()

    # Look for attributes that start with 'test_' and add them to the test list
    for attrname, attr in module.__dict__.items():
        if attrname.startswith('test_') and callable(attr):
            _tests.append(attr)

def testString(poentry):
    """Run all tests against the given translatable string.

       :param polib.POEntry poentry: The PO file entry to test
       :returns: whether the tests succeeded or not
       :rtype: bool
    """
    success = True
    for test in _tests:
        try:
            test(poentry)
        except Exception as e: # pylint: disable=broad-except
            success = False
            print("%s failed on %s: %s" % (test.__name__, poentry.msgid, str(e)))

    return success

def testPOT(potfile):
    """Run all tests against all entries in a POT file.

       :param str potfile: The name of a .pot file to test
       :return: whether the checks succeeded or not
       :rtype: bool
    """
    success = True

    parsed_pot = polib.pofile(potfile)

    for entry in parsed_pot:
        if not testString(entry):
            success = False

    return success
