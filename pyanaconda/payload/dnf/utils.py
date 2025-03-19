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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import operator

from blivet.size import Size

from pyanaconda.anaconda_loggers import get_packaging_logger
from pyanaconda.payload.dnf.transaction_progress import TransactionProgress
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf

log = get_packaging_logger()

DNF_PACKAGE_CACHE_DIR_SUFFIX = 'dnf.package.cache'
YUM_REPOS_DIR = "/etc/yum.repos.d/"


def get_df_map():
    """Return (mountpoint -> size available) mapping."""
    output = util.execWithCapture('df', ['--output=target,avail'])
    output = output.rstrip()
    lines = output.splitlines()
    structured = {}
    for line in lines:
        key, val = line.rsplit(maxsplit=1)
        if not key.startswith('/'):
            continue
        structured[key] = Size(int(val) * 1024)

    # Add /var/tmp/ if this is a directory or image installation
    if not conf.target.is_hardware:
        var_tmp = os.statvfs("/var/tmp")
        structured["/var/tmp"] = Size(var_tmp.f_frsize * var_tmp.f_bfree)
    return structured


def pick_mount_point(df, download_size, install_size, download_only):
    reasonable_mpoints = {
        '/var/tmp',
        conf.target.system_root,
        os.path.join(conf.target.system_root, 'home'),
        os.path.join(conf.target.system_root, 'tmp'),
        os.path.join(conf.target.system_root, 'var'),
    }

    requested = download_size
    requested_root = requested + install_size
    root_mpoint = conf.target.system_root
    log.debug('Input mount points: %s', df)
    log.info('Estimated size: download %s & install %s', requested,
             (requested_root - requested))

    # Find sufficient mountpoint to download and install packages.
    sufficients = {key: val for (key, val) in df.items()
                   if ((key != root_mpoint and val > requested) or val > requested_root) and
                   key in reasonable_mpoints}

    # If no sufficient mountpoints for download and install were found and we are looking
    # for download mountpoint only, ignore install size and try to find mountpoint just
    # to download packages. This fallback is required when user skipped space check.
    if not sufficients and download_only:
        sufficients = {key: val for (key, val) in df.items() if val > requested and
                       key in reasonable_mpoints}
        if sufficients:
            log.info('Sufficient mountpoint for download only found: %s', sufficients)
    elif sufficients:
        log.info('Sufficient mountpoints found: %s', sufficients)

    if not sufficients:
        log.debug("No sufficient mountpoints found")
        return None

    sorted_mpoints = sorted(sufficients.items(), key=operator.itemgetter(1), reverse=True)

    # try to pick something else than root mountpoint for downloading
    if download_only and len(sorted_mpoints) >= 2 and sorted_mpoints[0][0] == root_mpoint:
        return sorted_mpoints[1][0]
    else:
        # default to the biggest one:
        return sorted_mpoints[0][0]


def do_transaction(base, queue_instance):
    # Execute the DNF transaction and catch any errors. An error doesn't
    # always raise a BaseException, so presence of 'quit' without a preceeding
    # 'post' message also indicates a problem.
    try:
        display = TransactionProgress(queue_instance)
        base.do_transaction(display=display)
        exit_reason = "DNF quit"
    except BaseException as e:  # pylint: disable=broad-except
        log.error('The transaction process has ended abruptly')
        log.info(e)
        import traceback
        exit_reason = str(e) + traceback.format_exc()
    finally:
        base.close()  # Always close this base.
        queue_instance.put(('quit', str(exit_reason)))
