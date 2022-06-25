# Wrappers for GLib functions.
#
# Use these only if there is no other abstraction above the low level glib
# functions.
#
# Copyright (C) 2018 Red Hat, Inc.
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
#  Author(s):  Jiri Konecny <jkonecny@redhat.com>
#

import gi
gi.require_version("GLib", "2.0")

from gi.repository.GLib import markup_escape_text, format_size_full, \
                               timeout_add_seconds, timeout_add, idle_add, \
                               io_add_watch, child_watch_add, \
                               source_remove, \
                               spawn_close_pid, spawn_async_with_pipes, \
                               MainLoop, MainContext, \
                               GError, Variant, VariantType, Bytes, \
                               IOCondition, IOChannel, SpawnFlags, \
                               MAXUINT

__all__ = ["create_main_loop", "create_new_context", "mainloop_run"
           "markup_escape_text", "format_size_full",
           "timeout_add_seconds", "timeout_add", "idle_add",
           "io_add_watch", "child_watch_add",
           "source_remove",
           "spawn_close_pid", "spawn_async_with_pipes",
           "GError", "Variant", "VariantType", "Bytes",
           "IOCondition", "IOChannel", "SpawnFlags",
           "MAXUINT"]


def create_main_loop(mainctx=None):
    """Create GLib main loop.

    :param mainctx: create a mainloop with mainctx
    :returns: GLib.MainLoop instance.
    """
    return MainLoop(mainctx)


def create_new_context():
    """Create GLib context.

    :returns: GLib.MainContext."""
    return MainContext.new()


def mainloop_run(timeout=0, mainloop=None):
    if mainloop is None:
        mainloop = MainLoop()

    timeout_id = None
    timeout_reached = []

    if timeout > 0:

        def _timeout_cb(unused):
            # it can happen that the caller already quit the mainloop
            # otherwise. In that case, we don't want to signal a timeout.
            if mainloop.is_running():
                timeout_reached.append(1)
                mainloop.quit()
            return True

        timeout_id = timeout_add(timeout, _timeout_cb, None)

    mainloop.run()
    if timeout_id:
        source_remove(timeout_id)

    return not timeout_reached
