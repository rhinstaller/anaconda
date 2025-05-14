#!/usr/bin/python3
#
# Run Anaconda DBus services locally in separate DBus session.
#
# This script is mainly for debugging purpose.
#

import argparse
import glob
import os
import shutil
import sys
import tempfile
import time

from dasbus.connection import AddressedMessageBus
from gi.repository import Gio

from pyanaconda.modules.common.constants.services import BOSS
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.common.task import sync_run_task

try:
    from colorama import Fore, Style
    GREEN = Fore.GREEN
    RED = Fore.RED
    RESET = Style.RESET_ALL
except ImportError as e:
    print("#########################################")
    print("Install python3-colorama for nicer output")
    print("#########################################")
    GREEN = ""
    RED = ""
    RESET = ""


# add project top directory to the python paths
top_dir = os.path.dirname(os.path.realpath(__file__))
top_dir = os.path.split(top_dir)[0]
sys.path.insert(0, top_dir)

# add top dir to the PYTHONPATH env var for Boss and modules
paths = os.environ.get("PYTHONPATH", "").split(":")
paths.insert(0, top_dir)
os.putenv("PYTHONPATH", ":".join(paths))  # pylint: disable=environment-modify

MODULES_DIR = os.path.join(top_dir ,"pyanaconda/modules")
DBUS_SERVICES_DIR = os.path.join(top_dir, "data/dbus/")
STARTUP_SCRIPT = os.path.join(top_dir, "scripts/start-module")
EXEC_PATH = 'Exec=/usr/libexec/anaconda/start-module'


def start_anaconda_services():
    print(RED + "starting Boss" + RESET)
    bus_proxy = test_dbus_connection.proxy
    bus_proxy.StartServiceByName(BOSS.service_name, 0)

    boss_proxy = test_dbus_connection.get_proxy(BOSS.service_name, BOSS.object_path)
    task_path = boss_proxy.StartModulesWithTask()
    task_proxy = test_dbus_connection.get_proxy(BOSS.service_name, task_path)
    sync_run_task(task_proxy)

def distribute_kickstart(ks_path):
    tmpfile = tempfile.mktemp(suffix=".run_boss_locally.ks")
    shutil.copyfile(ks_path, tmpfile)
    print(RED + "distributing kickstart {}".format(tmpfile) + RESET)
    boss_object = test_dbus_connection.get_proxy(BOSS.service_name, BOSS.object_path)
    try:
        report = KickstartReport.from_structure(
            boss_object.ReadKickstartFile(tmpfile)
        )
        print("distribute_kickstart: ReadKickstartFile() errors: {}".format(str(report)))
    finally:
        os.unlink(tmpfile)

def stops_anaconda_services():
    print(RED + "stopping Boss" + RESET)

    boss_object = test_dbus_connection.get_proxy(BOSS.service_name, BOSS.object_path)
    boss_object.Quit()

    print(RED + "waiting a bit for module shutdown to happen" + RESET)
    time.sleep(1)

parser=argparse.ArgumentParser(description="Run Boss DBus service locally on testing Bus")
parser.add_argument('-k', '--kickstart', action='store', type=str,
                    help='distribute kickstart to modules')
args = parser.parse_args()
if args.kickstart and not os.path.exists(args.kickstart):
    print("ERROR: kickstart file {} not found".format(args.kickstart))

print("creating a temporary directory for DBus service files")
temp_service_dir = tempfile.TemporaryDirectory(prefix="anaconda_dbus_")
print(temp_service_dir.name)

print("copying & modifying DBus service files")
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
    # start the custom DBus daemon
    print("starting custom dbus session")
    test_dbus.up()

    # our custom bus is now running, connect to it
    test_dbus_connection = AddressedMessageBus(test_dbus.get_bus_address())

    enter_word = GREEN + "enter" + RESET
    q_word = GREEN + "q" + RESET
    print("")
    print("###########################################################################")
    print("Connect to the bus address below [press a key to continue]:")
    print("(guid part may be ignored)")
    print(GREEN + test_dbus_connection.address + RESET)
    if args.kickstart:
        print()
        print("Kickstart file {} will be distributed to modules.".format(args.kickstart))
    print()
    print("To control the loop press " + enter_word + " to restart Boss or [" + q_word + "] to Quit session")
    print("###########################################################################")

    input()

    loop = True

    while(loop):
        start_anaconda_services()

        if args.kickstart:
            distribute_kickstart(args.kickstart)

        u_input = input()

        stops_anaconda_services()

        if u_input == "q":
            loop = False

finally:
    # stop the custom DBus daemon
    print("stopping custom dbus session")
    test_dbus.down()

# cleanup
print("cleaning up")
temp_service_dir.cleanup()
# done
print("done")
