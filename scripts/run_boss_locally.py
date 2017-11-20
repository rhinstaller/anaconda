#!/usr/bin/python3

import os
import tempfile
import shutil
import glob
import pydbus
import time
from gi.repository import Gio

from pyanaconda.dbus import dbus_constants

os.putenv("PYTHONPATH", os.path.abspath(".."))  # pylint: disable=environment-modify

MODULES_DIR = os.path.abspath("../pyanaconda/modules")
DBUS_SERVICES_DIR = "../data/dbus/"

print("creating a temporary directory for DBUS service files")
temp_service_dir = tempfile.TemporaryDirectory(prefix="anaconda_dbus_")
print(temp_service_dir.name)

print("copying service files")
for file_path in glob.glob(DBUS_SERVICES_DIR +  "*.service"):
    filename = os.path.split(file_path)[1]
    target_file_path = os.path.join(temp_service_dir.name, filename)
    shutil.copy(file_path, target_file_path)

test_dbus = Gio.TestDBus()

# set service folder
test_dbus.add_service_dir(temp_service_dir.name)

try:
    # start the custom DBUS daemon
    print("starting custom dbus session")
    test_dbus.up()
    print(test_dbus.get_bus_address())

    # our custom bus is now running, connect to it
    test_dbus_connection = pydbus.connect(test_dbus.get_bus_address())

    print("starting Boss")
    test_dbus_connection.dbus.StartServiceByName(dbus_constants.DBUS_BOSS_NAME, 0)

    input("press any key to stop Boss and cleanup")

    print("stopping Boss")

    boss_object = test_dbus_connection.get(dbus_constants.DBUS_BOSS_NAME)
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
