#!/usr/bin/python3

import nose
import os
import sys
import glob

from gladecheck import GladePlugin

# Check for prerequisites
# used in check_icons.py via tests/lib/iconcheck.py
if os.system("rpm -q adwaita-icon-theme >/dev/null 2>&1") != 0:
    print("adwaita-icon-theme must be installed")
    sys.exit(99)

# If no test scripts were specified on the command line, select check_*.py
if len(sys.argv) <= 1 or not sys.argv[-1].endswith('.py'):
    sys.argv.extend(glob.glob(os.path.dirname(sys.argv[0]) + "/check_*.py"))

# Run in verbose mode
sys.argv.append('-v')

# Run nose with the glade plugin
nose.main(addplugins=[GladePlugin()])
