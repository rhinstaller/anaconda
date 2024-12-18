#
# shutup.py: context manager for ignoring overly verbose output
#
# Copyright (C) 2015  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from contextlib import contextmanager


@contextmanager
def shutup():
    """Run something with stdout and stderr redirected to /dev/null

       The redirections will be process-wide, so this is not recommended
       for multithreaded applications.
    """

    # Wrap the whole thing a try-finally to ensure errors don't leak file descriptor
    old_stdout = None
    old_stderr = None
    devnull_fd = None

    try:
        # Save the current file descriptors
        old_stdout = os.dup(1)
        old_stderr = os.dup(2)

        # Redirect to /dev/null
        # Try to undo partial redirects if something goes wrong
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(devnull_fd, 1)
            os.dup2(devnull_fd, 2)
        except:
            os.dup2(old_stderr, 2)
            os.dup2(old_stdout, 1)
            raise

        # Run the body. Cleanup in finally to ensure stderr is restored before
        # an exception is raised.
        try:
            yield
        finally:
            os.dup2(old_stderr, 2)
            os.dup2(old_stdout, 1)

    finally:
        if old_stdout is not None:
            os.close(old_stdout)
        if old_stderr is not None:
            os.close(old_stderr)
        if devnull_fd is not None:
            os.close(devnull_fd)
