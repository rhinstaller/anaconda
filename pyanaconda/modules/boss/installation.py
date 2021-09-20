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
from pyanaconda.core.util import execWithRedirect, join_paths, mkdirChain
from pyanaconda.modules.common.task import Task

log = get_module_logger(__name__)

ANACONDA_LOG_DIR = "/var/log/anaconda/"


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
        self._copy_logs()
        self._copy_kickstart()
        self._relabel_files()

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
        self._chmod_logs()

    def _create_logs_directory(self):
        """Create directory for Anaconda logs on the install target"""
        mkdirChain(join_paths(self._sysroot, ANACONDA_LOG_DIR))

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
                join_paths(ANACONDA_LOG_DIR, logfile)
            )

    def _copy_lorax_packages(self):
        """Copy list of packages used for creating the installation media"""
        self._copy_file_to_sysroot(
            "/root/lorax-packages.log",
            join_paths(ANACONDA_LOG_DIR, "lorax-packages.log")
        )

    def _copy_pre_script_logs(self):
        """Copy logs from %pre scripts"""
        self._copy_tree_to_sysroot(
            "/tmp/pre-anaconda-logs",
            ANACONDA_LOG_DIR
        )

    def _copy_dnf_debugdata(self):
        """Copy DNF debug data"""
        self._copy_tree_to_sysroot(
            "/root/debugdata",
            join_paths(ANACONDA_LOG_DIR, "dnf_debugdata/")
        )

    def _copy_post_script_logs(self):
        """Copy logs from %post scripts"""
        for logfile in glob.glob("/tmp/ks-script*.log"):
            self._copy_file_to_sysroot(
                logfile,
                join_paths(ANACONDA_LOG_DIR, os.path.basename(logfile))
            )

    def _dump_journal(self):
        """Dump journal from the installation environment"""
        with open(join_paths(self._sysroot, ANACONDA_LOG_DIR, "journal.log"), "w") as logfile:
            execWithRedirect("journalctl", ["-b"], stdout=logfile)

    def _chmod_logs(self):
        """Set access bits"""
        items = glob.glob(join_paths(self._sysroot, ANACONDA_LOG_DIR, '*'))
        for item in items:
            os.chmod(item, 0o0600)

    def _copy_kickstart(self):
        """Copy input kickstart file"""
        if conf.target.can_copy_input_kickstart:
            log.info("Copying input kickstart file.")
            self._copy_file_to_sysroot(
                "/run/install/ks.cfg",
                "/root/original-ks.cfg"
            )
            os.chmod(join_paths(self._sysroot, "/root/original-ks.cfg"), 0o0600)
        else:
            log.warning("Input kickstart will not be saved to the installed system due to the "
                        "nosave option.")

    def _relabel_files(self):
        """Relabel the anaconda logs.

        The files we've just copied could be incorrectly labeled, like hawkey.log:
        https://bugzilla.redhat.com/show_bug.cgi?id=1885772
        """
        execWithRedirect("restorecon", ["-ir", ANACONDA_LOG_DIR], root=self._sysroot)

    def _copy_file_to_sysroot(self, src, dest):
        """Copy a file, if it exists.

        :param str src: path to source file
        :param str dest: path to destination file within sysroot
        """
        if os.path.exists(src):
            log.info("Copying file: %s -> %s", src, dest)
            shutil.copyfile(
                src,
                join_paths(self._sysroot, dest)
            )

    def _copy_tree_to_sysroot(self, src, dest):
        """Copy a directory tree, if it exists.

        :param str src: path to source directory
        :param str dest: path to destination directory within sysroot
        """
        if os.path.exists(src):
            log.info("Copying directory tree: %s -> %s", src, dest)
            shutil.copytree(
                src,
                join_paths(self._sysroot, dest),
                dirs_exist_ok=True
            )
