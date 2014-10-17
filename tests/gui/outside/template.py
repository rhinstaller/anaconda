# pylint: skip-file
#
# Copyright (C) 2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>

# This code template ends up being the special suite.py file referred to in the
# Creator.makeSuite documentation.  It lives in the suite disk image and is
# automatically started by the live CD on boot (see the kickstart file for where
# this happens).  Basically, this is responsible for doing everything inside the
# VM - it runs the test suite, figures out whether it failed or not, puts results
# in place, and reboots.

from dogtail import utils
utils.enableA11y()

import glob
import os
import shlex
import shutil
import traceback
import unittest

class UITestSuite(unittest.TestSuite):
    def run(self, *args, **kwargs):
        utils.run("liveinst %(anacondaArgs)s")
        unittest.TestSuite.run(self, *args, **kwargs)

def suite():
%(imports)s

    s = UITestSuite()
%(addtests)s
    return s

if __name__ == "__main__":
%(environ)s

    s = suite()
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(s)

    try:
        if not result.wasSuccessful():
            with open("/mnt/anactest/result/unittest-failures", "w") as f:
                for (where, what) in result.errors + result.failures:
                    f.write(str(where) + "\n" + str(what) + "\n")

                f.close()

        for log in glob.glob("/tmp/*.log"):
            shutil.copy(log, "/mnt/anactest/result/anaconda/")

        if os.path.exists("/tmp/memory.dat"):
            shutil.copy("/tmp/memory.dat", "/mnt/anactest/result/anaconda/")

        # anaconda writes out traceback files with restricted permissions, so
        # we have to go out of our way to grab them.
        for tb in glob.glob("/tmp/anaconda-tb-*"):
            os.system("sudo cp " + tb + " /mnt/anactest/result/anaconda/")
    except:
        # If anything went wrong with the above, log it and quit.  We need
        # this VM to always turn off so we can inspect what happened.
        with open("/mnt/anactest/result/unittest-failures", "w+") as f:
            traceback.print_exc(file=f)
            f.close()

    os.system("poweroff")
