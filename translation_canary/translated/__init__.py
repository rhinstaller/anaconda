# Framework for testing translations
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
Framework for running tests against translations.

Tests are loaded from modules in this directory. A test is any callable object
within the module with a name that starts with 'test_'.

Each test is called with the name of .po file to test as an argument. A test
passes if it returns without raising an exception.
"""

import os, warnings

_tests = []

# Gather tests from this directory
import pkgutil
for finder, mod_name, _ispkg in pkgutil.iter_modules(__path__):
    # Skip __main__
    if mod_name == "__main__":
        continue

    # Load the module
    module = finder.find_module(mod_name).load_module(mod_name)

    # Look for attributes that start with 'test_' and add them to the test list
    for attrname, attr in module.__dict__.items():
        if attrname.startswith('test_') and callable(attr):
            _tests.append(attr)

def _remove_lingua(linguas, language):
    # Read in the LINGUAS file
    with open(linguas, "rt") as f:
        lingua_lines = f.readlines()

    output_lines = []
    for line in lingua_lines:
        # Leave comments alone
        if line.startswith('#'):
            output_lines.append(line)
            continue

        # Split the line into a list of languages, remove the one we don't
        # want, and put it back together
        lingua_list = line.split()
        lingua_list.remove(language)
        output_lines.append(" ".join(lingua_list))

    # Write LINGUAS back out
    with open(linguas, "wt") as f:
        f.writelines(output_lines)

def testFile(pofile, prefix=None, releaseMode=False, modifyLinguas=True):
    """Run all registered tests against the given .mo file.

       If run in release mode, this function will always return true, and if
       the mofile does not pass the tests the langauge will be removed.

       :param str mofile: The .mo file name to check
       :param str prefix: An optional directory prefix to strip from error messages
       :param bool releaseMode: whether to run in release mode
       :param bool modifyLinguas: whether to remove translations from LINGUAS in release mode
       :return: whether the checks succeeded or not
       :rtype: bool
    """
    success = True
    for test in _tests:
        # Don't print the tmpdir path in error messages
        if prefix is not None and pofile.startswith(prefix):
            poerror = pofile[len(prefix):]
        else:
            poerror = pofile

        try:
            with warnings.catch_warnings(record=True) as w:
                test(pofile)

                # Print any warnings collected
                for warn in w:
                    print("%s warned on %s: %s" % (test.__name__, poerror, warn.message))
        except Exception as e: # pylint: disable=broad-except
            print("%s failed on %s: %s" % (test.__name__, poerror, str(e)))
            if releaseMode:
                # Remove the po file and the .mo file built from it
                print("Removing %s" % pofile)
                os.remove(pofile)

                # Check for both .mo and .gmo
                mofile = os.path.splitext(pofile)[0] + '.mo'
                if os.path.exists(mofile):
                    print("Removing %s" % mofile)
                    os.remove(mofile)

                gmofile = os.path.splitext(pofile)[0] + '.gmo'
                if os.path.exists(gmofile):
                    print("Removing %s" % gmofile)
                    os.remove(gmofile)

                if modifyLinguas:
                    # If there is a LINGUAS file in the po directory, remove the
                    # language from it
                    linguas = os.path.join(os.path.dirname(mofile), 'LINGUAS')
                    if os.path.exists(linguas):
                        language = os.path.splitext(os.path.basename(pofile))[0]
                        print("Removing %s from LINGUAS" % language)
                        _remove_lingua(linguas, language)

                # No need to run the rest of the tests since we just killed the file
                break
            else:
                success = False

    return success

def testSourceTree(srcdir, releaseMode=False, modifyLinguas=True):
    """Runs all registered tests against all .po files in the given directory.

       If run in release mode, this function will always return True and the
       languages that do not pass the tests will be removed.

       :param str srcdir: The path to the source directory to check
       :param bool releaseMode: whether to run in release mode
       :param bool modifyLinguas: whether to remove translations from LINGUAS in release mode
       :return: whether the checks succeeded or not
       :rtype: bool
    """
    success = True
    srcdir = os.path.normpath(srcdir)

    for dirpath, _dirnames, paths in os.walk(srcdir):
        for pofile in (os.path.join(dirpath, path) for path in paths if path.endswith('.po')):
            if not testFile(pofile, prefix=srcdir + "/", releaseMode=releaseMode, modifyLinguas=modifyLinguas):
                success = False

    return success
