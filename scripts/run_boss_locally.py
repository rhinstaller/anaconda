#!/usr/bin/python3
#
# Run Anaconda DBus services locally in separate DBus session.
#
# This script is mainly for debugging purpose.
#

import os
import tempfile
import glob
import pydbus
import time
import sys
from gi.repository import Gio

try:
    from colorama import Fore, Style
    GREEN = Fore.GREEN
    RESET = Style.RESET_ALL
except ImportError as e:
    print("#########################################")
    print("Install python3-colorama for nicer output")
    print("#########################################")
    GREEN = ""
    RESET = ""


# add project top directory to the python paths
top_dir = os.path.dirname(os.path.realpath(__file__))
top_dir = os.path.split(top_dir)[0]
sys.path.insert(0, top_dir)

# add top dir to the PYTHONPATH env var for Boss and modules
paths = os.environ.get("PYTHONPATH", "").split(":")
paths.insert(0, top_dir)
os.putenv("PYTHONPATH", ":".join(paths))  # pylint: disable=environment-modify

from pyanaconda.dbus.constants import DBUS_BOSS_NAME

MODULES_DIR = os.path.join(top_dir ,"pyanaconda/modules")
DBUS_SERVICES_DIR = os.path.join(top_dir, "data/dbus/")
STARTUP_SCRIPT = os.path.join(top_dir, "scripts/start-module")
EXEC_PATH = 'Exec=/usr/libexec/anaconda/start-module'

print("creating a temporary directory for DBUS service files")
temp_service_dir = tempfile.TemporaryDirectory(prefix="anaconda_dbus_")
print(temp_service_dir.name)

print("copying & modifying DBUS service files")
modified_exec_path = 'Exec={}'.format(STARTUP_SCRIPT)
for file_path in glob.glob(DBUS_SERVICES_DIR +  "*.service"):
    filename = os.path.split(file_path)[1]
    target_file_path = os.path.join(temp_service_dir.name, filename)
    with open(file_path, "rt") as input_file:
        with open(target_file_path, "wt") as output_file:
            for line in input_file:
                # change path to the startup script to point to local copy
                output_file.write(line.replace(EXEC_PATH, modified_exec_path))

test_dbus = Gio.TestDBus()

# set service folder
test_dbus.add_service_dir(temp_service_dir.name)

try:
    # start the custom DBUS daemon
    print("starting custom dbus session")
    test_dbus.up()

    # our custom bus is now running, connect to it
    test_dbus_connection = pydbus.connect(test_dbus.get_bus_address())

    print("")
    print("###########################################################################")
    print("Connect to the bus address below [press a key to continue]:")
    print("(guid part may be ignored)")
    print(GREEN + test_dbus.get_bus_address() + RESET)
    print("###########################################################################")

    input()

    print("starting Boss")
    test_dbus_connection.dbus.StartServiceByName(DBUS_BOSS_NAME, 0)


    input("press any key to stop Boss and cleanup")

    print("stopping Boss")

    boss_object = test_dbus_connection.get(DBUS_BOSS_NAME)
    boss_object.Quit()

    print("waiting a bit for module shutdown to happen")
    time.sleep(1)

finally:
    # stop the custom DBUS daemon
    print("stopping custom dbus session")
    test_dbus.down()

# cleanup
print("cleaning up")
temp_service_dir.cleanup()
# done
print("done")
