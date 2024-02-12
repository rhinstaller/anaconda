#
# Copyright (C) 2021 Red Hat, Inc.
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
import os.path
import shutil
import glob

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.path import make_directories, join_paths, open_with_perm
from pyanaconda.core.util import execWithRedirect, restorecon
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

TARGET_LOG_DIR = "/var/log/anaconda/"


class CopyLogsTask(Task):
    """Task to copy logs to target system."""
    def __init__(self, sysroot):
        """Create a new task.

        :param sysroot: a path to the root of installed system
        :type sysroot: str
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Copy installation logs"

    def run(self):
        """Copy installation logs and other related files, and do necessary operations on them.

        - Copy logs of all kinds, incl. ks scripts, journal dump, and lorax pkg list
        - Copy input kickstart file
        - Autorelabel everything in the destination
        """
        self._copy_kickstart()
        self._copy_logs()

    def _copy_logs(self):
        """Copy installation logs to the target system"""
        if not conf.target.can_save_installation_logs:
            log.warning("Installation logs will not be saved to the installed system due to the "
                        "nosave option.")
            return

        log.info("Copying logs from the installation environment.")
        self._create_logs_directory()
        self._copy_tmp_logs()
        self._copy_lorax_packages()
        self._copy_pre_script_logs()
        self._copy_dnf_debugdata()
        self._copy_post_script_logs()
        self._dump_journal()
        self._relabel_log_files()

    def _create_logs_directory(self):
        """Create directory for Anaconda logs on the install target"""
        make_directories(join_paths(self._sysroot, TARGET_LOG_DIR))

    def _copy_tmp_logs(self):
        """Copy a number of log files from /tmp"""
        log_files_to_copy = [
            "anaconda.log",
            "syslog",
            "X.log",
            "program.log",
            "packaging.log",
            "storage.log",
            "ifcfg.log",
            "lvm.log",
            "dnf.librepo.log",
            "hawkey.log",
            "dbus.log",
        ]
        for logfile in log_files_to_copy:
            self._copy_file_to_sysroot(
                join_paths("/tmp/", logfile),
                join_paths(TARGET_LOG_DIR, logfile)
            )

    def _copy_lorax_packages(self):
        """Copy list of packages used for creating the installation media"""
        self._copy_file_to_sysroot(
            "/root/lorax-packages.log",
            join_paths(TARGET_LOG_DIR, "lorax-packages.log")
        )

    def _copy_pre_script_logs(self):
        """Copy logs from %pre scripts"""
        self._copy_tree_to_sysroot(
            "/tmp/pre-anaconda-logs",
            TARGET_LOG_DIR
        )

    def _copy_dnf_debugdata(self):
        """Copy DNF debug data"""
        self._copy_tree_to_sysroot(
            "/root/debugdata",
            join_paths(TARGET_LOG_DIR, "dnf_debugdata/")
        )

    def _copy_post_script_logs(self):
        """Copy logs from %post scripts"""
        for logfile in glob.glob("/tmp/ks-script*.log"):
            self._copy_file_to_sysroot(
                logfile,
                join_paths(TARGET_LOG_DIR, os.path.basename(logfile))
            )

    def _dump_journal(self):
        """Dump journal from the installation environment"""
        tempfile = "/tmp/journal.log"
        with open_with_perm(tempfile, "w", perm=0o600) as logfile:
            execWithRedirect("journalctl", ["-b"], stdout=logfile, log_output=False)
        self._copy_file_to_sysroot(tempfile, join_paths(TARGET_LOG_DIR, "journal.log"))

    def _copy_kickstart(self):
        """Copy input kickstart file"""
        if conf.target.can_copy_input_kickstart:
            log.info("Copying input kickstart file.")
            self._copy_file_to_sysroot(
                "/run/install/ks.cfg",
                "/root/original-ks.cfg"
            )
        else:
            log.warning("Input kickstart will not be saved to the installed system due to the "
                        "nosave option.")

    def _relabel_log_files(self):
        """Relabel the anaconda logs.

        The files we've just copied could be incorrectly labeled, like hawkey.log:
        https://bugzilla.redhat.com/show_bug.cgi?id=1885772
        """
        if not restorecon([TARGET_LOG_DIR], root=self._sysroot, skip_nonexistent=True):
            log.error("Log file contexts were not restored because restorecon was not installed.")

    def _copy_file_to_sysroot(self, src, dest):
        """Copy a file, if it exists, and set its access bits.

        :param str src: path to source file
        :param str dest: path to destination file within sysroot
        """
        if os.path.exists(src):
            log.info("Copying file: %s -> %s", src, dest)
            full_dest_path = join_paths(self._sysroot, dest)
            shutil.copyfile(
                src,
                full_dest_path
            )
            os.chmod(full_dest_path, 0o0600)

    def _copy_tree_to_sysroot(self, src, dest):
        """Copy a directory tree, if it exists, and set its access bits.

        :param str src: path to source directory
        :param str dest: path to destination directory within sysroot
        """
        if os.path.exists(src):
            log.info("Copying directory tree: %s -> %s", src, dest)
            full_dest_path = join_paths(self._sysroot, dest)
            shutil.copytree(
                src,
                full_dest_path,
                dirs_exist_ok=True
            )
            os.chmod(full_dest_path, 0o0600)


class SetContextsTask(Task):
    """Task to set file contexts on target system.

    We need to handle SELinux relabeling for a few reasons:

    - %post scripts that write files into places in /etc, but don't do labeling correctly
    - Anaconda code that does the same (e.g. moving our log files into /var/log/anaconda)
    - ostree payloads, where all of the labeling of /var is the installer's responsibility
      (see https://github.com/ostreedev/ostree/pull/872 )
    - OSTree variants of the traditional mounts if present
    """
    def __init__(self, sysroot):
        """Create a new task.

        :param sysroot: a path to the root of installed system
        :type sysroot: str
        """
        super().__init__()
        self._sysroot = sysroot

    @property
    def name(self):
        return "Set file contexts"

    def run(self):
        """Relabel files (set contexts).

        Do not fail if the executable is not present.
        """
        dirs_to_relabel = [
            "/boot",
            "/dev",
            "/etc",
            "/lib64",
            "/root",
            "/usr/lib",
            "/usr/lib64",
            "/var/cache/yum",
            "/var/home",
            "/var/lib",
            "/var/lock",
            "/var/log",
            "/var/media",
            "/var/mnt",
            "/var/opt",
            "/var/roothome",
            "/var/run",
            "/var/spool",
            "/var/srv"
        ]

        log.info("Restoring SELinux contexts.")
        if not restorecon(dirs_to_relabel, root=self._sysroot, skip_nonexistent=True):
            log.warning("Cannot restore contexts because restorecon was not installed.")
