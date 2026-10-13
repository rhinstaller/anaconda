# Copyright (C) Ctrl IQ, Inc.
# SPDX-License-Identifier: GPL-2.0-or-later

import io
import logging
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from pyanaconda.modules.common import init


def _is_locked_elsewhere(lock):
    """Return True if another thread cannot take the lock now."""
    taken = []

    def probe():
        if lock.acquire(blocking=False):
            lock.release()
            taken.append(True)

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return not taken


class InitLoggingTestCase(unittest.TestCase):
    """Test the logging configured by init()."""

    @patch("locale.setlocale")
    @patch("faulthandler.enable")
    @patch("logging.basicConfig")
    def test_handlers_not_locked_during_format(self, basic_config, enable_faulthandler, set_locale):
        """Test that the handlers format log arguments without holding their lock.

        Blivet objects take blivet_lock when converted to a string.
        A handler that holds its lock while formatting them can deadlock
        against a thread that holds blivet_lock and logs.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = os.path.join(tmp_dir, "module.log")
            init(log_filename=log_file, log_stream=io.StringIO())
            handlers = basic_config.call_args.kwargs["handlers"]

            locked = []

            class Device:
                def __str__(self):
                    locked.extend(_is_locked_elsewhere(h.lock) for h in handlers)
                    return "device"

            record = logging.makeLogRecord({"msg": "%s", "args": (Device(),)})
            for handler in handlers:
                handler.handle(record)
                handler.close()

            assert locked, "the message was not formatted"
            assert not any(locked)
