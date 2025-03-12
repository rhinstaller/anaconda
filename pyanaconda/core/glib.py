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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
#  Author(s):  Jiri Konecny <jkonecny@redhat.com>
#

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")

from gi.repository.Gio import Cancellable
from gi.repository.GLib import (
    MAXUINT,
    Bytes,
    GError,
    IOChannel,
    IOCondition,
    LogLevelFlags,
    LogWriterOutput,
    MainContext,
    MainLoop,
    SpawnFlags,
    Variant,
    VariantType,
    child_watch_add,
    format_size_full,
    idle_add,
    io_add_watch,
    log_set_handler,
    log_set_writer_func,
    log_writer_format_fields,
    markup_escape_text,
    source_remove,
    spawn_async_with_pipes,
    spawn_close_pid,
    timeout_add,
    timeout_add_seconds,
    timeout_source_new,
)

from pyanaconda.anaconda_loggers import get_module_logger

log = get_module_logger(__name__)


__all__ = [
    "MAXUINT",
    "Bytes",
    "Cancellable",
    "GError",
    "IOChannel",
    "IOCondition",
    "LogLevelFlags",
    "LogWriterOutput",
    "SpawnFlags",
    "Variant",
    "VariantType",
    "child_watch_add",
    "create_main_loop",
    "create_new_context",
    "format_size_full",
    "idle_add",
    "io_add_watch",
    "log_set_handler",
    "log_set_writer_func",
    "log_writer_format_fields",
    "markup_escape_text",
    "source_remove",
    "spawn_async_with_pipes",
    "spawn_close_pid",
    "timeout_add",
    "timeout_add_seconds",
    "timeout_source_new",
]


def create_main_loop(main_context=None):
    """Create GLib main loop.

    :param main_context: main context to be used for the loop
    :type main_context: GLib.MainContext
    :returns: GLib.MainLoop instance.
    """
    return MainLoop(main_context)


def create_new_context():
    """Create GLib context.

    :returns: GLib.MainContext."""
    return MainContext.new()


class GLibCallResult():
    """Result of GLib async finish callback."""
    def __init__(self):
        self.received_data = None
        self.error_message = ""
        self.timeout = False

    @property
    def succeeded(self):
        """The async call has succeeded."""
        return not self.failed

    @property
    def failed(self):
        """The async call has failed."""
        return bool(self.error_message) or self.timeout


def sync_call_glib(context, async_call, async_call_finish, timeout, *call_args):
    """Call GLib asynchronous method synchronously with timeout.

    :param context: context for the new loop in which the method will be called
    :type context: GMainContext
    :param async_call: asynchronous GLib method to be called
    :type async_call: GLib method
    :param async_call_finish: finish method of the asynchronous call
    :type async_call_finish: GLib method
    :param timeout: timeout for the loop in seconds (0 == no timeout)
    :type timeout: int

    *call_args should hold all positional arguments preceding the cancellable argument
    """

    info = async_call.get_symbol()
    result = GLibCallResult()

    loop = create_main_loop(context)
    callbacks = [loop.quit]

    def _stop_loop():
        log.debug("sync_call_glib[%s]: quit", info)
        while callbacks:
            callback = callbacks.pop()
            callback()

    def _cancellable_cb():
        log.debug("sync_call_glib[%s]: cancelled", info)

    cancellable = Cancellable()
    cancellable_id = cancellable.connect(_cancellable_cb)
    callbacks.append(lambda: cancellable.disconnect(cancellable_id))

    def _timeout_cb(user_data):
        log.debug("sync_call_glib[%s]: timeout", info)
        result.timeout = True
        cancellable.cancel()
        return False

    timeout_source = timeout_source_new(int(timeout * 1000))
    timeout_source.set_callback(_timeout_cb)
    timeout_source.attach(context)
    callbacks.append(timeout_source.destroy)

    def _finish_cb(_source_object, async_result):
        log.debug("sync_call_glib[%s]: call %s",
                  info,
                  async_call_finish.get_symbol())
        try:
            result.received_data = async_call_finish(async_result)
        except Exception as e:  # pylint: disable=broad-except
            result.error_message = str(e)
        finally:
            _stop_loop()

    context.push_thread_default()

    log.debug("sync_call_glib[%s]: call", info)
    try:
        async_call(
            *call_args,
            cancellable=cancellable,
            callback=_finish_cb
        )
        loop.run()
    finally:
        _stop_loop()
        context.pop_thread_default()

    return result
