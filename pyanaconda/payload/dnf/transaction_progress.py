#
# Copyright (C) 2020  Red Hat, Inc.
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
import dnf.callback
import dnf.transaction

__all__ = ["TransactionProgress"]


class TransactionProgress(dnf.callback.TransactionProgress):
    def __init__(self, queue_instance):
        super().__init__()
        self._queue = queue_instance
        self._last_ts = None
        self._postinst_phase = False
        self.cnt = 0

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        # Process DNF actions, communicating with anaconda via the queue
        # A normal installation consists of 'install' messages followed by
        # the 'post' message.
        if action == dnf.transaction.PKG_INSTALL and ti_done == 0:
            # do not report same package twice
            if self._last_ts == ts_done:
                return
            self._last_ts = ts_done

            msg = '%s.%s (%d/%d)' % \
                (package.name, package.arch, ts_done, ts_total)
            self.cnt += 1
            self._queue.put(('install', msg))

            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Installed: %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

        elif action == dnf.transaction.TRANS_POST:
            self._queue.put(('post', None))
            log_msg = "Post installation setup phase started."
            self._queue.put(('log', log_msg))
            self._postinst_phase = True

        elif action == dnf.transaction.PKG_SCRIPTLET:
            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Configuring (running scriptlet for): %s %s %s" % (nevra, package.buildtime,
                                                                         package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # only show progress in UI for post-installation scriptlets
            if self._postinst_phase:
                msg = '%s.%s' % (package.name, package.arch)
                self._queue.put(('configure', msg))

        elif action == dnf.transaction.PKG_VERIFY:
            msg = '%s.%s (%d/%d)' % (package.name, package.arch, ts_done, ts_total)
            self._queue.put(('verify', msg))

            # Log the exact package nevra, build time and checksum
            nevra = "%s-%s.%s" % (package.name, package.evr, package.arch)
            log_msg = "Verifying: %s %s %s" % (nevra, package.buildtime, package.returnIdSum()[1])
            self._queue.put(('log', log_msg))

            # Once the last package is verified the transaction is over
            if ts_done == ts_total:
                self._queue.put(('done', None))

    def error(self, message):
        """Report an error that occurred during the transaction. Message is a
        string which describes the error.
        """
        self._queue.put(('error', message))
