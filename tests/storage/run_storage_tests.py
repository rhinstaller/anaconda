#!/usr/bin/python

import os, sys

if os.geteuid() != 0:
    sys.stderr.write("You must be root to run the storage tests; skipping.\n")
    # This return code tells the automake test driver that this test was skipped.
    os._exit(77)

from cases.bz1014545 import BZ1014545_TestCase
from cases.bz1067707 import BZ1067707_TestCase

for tc in [BZ1014545_TestCase(),
           BZ1067707_TestCase()]:
    failures = tc.run()

os._exit(failures)
