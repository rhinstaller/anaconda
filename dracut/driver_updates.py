#!/usr/bin/python
#
# Copyright (C) 2015 by Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s):
#   Brian C. Lane <bcl@brianlane.com>
#   Will Woods <wwoods@redhat.com>
#
"""
Driver Update Disk handler program.

This will be called once for each requested driverdisk (non-interactive), and
once for interactive mode (if requested).

Usage is one of:

    driver-updates --disk DISKSTR DEVNODE

        DISKSTR is the string passed by the user ('/dev/sda3', 'LABEL=DD', etc.)
        DEVNODE is the actual device node (/dev/sda3, /dev/sr0, etc.)

    driver-updates --net URL LOCALFILE

        URL is the string passed by the user ('http://.../something.iso')
        LOCALFILE is the location of the downloaded file

    driver-updates --interactive

        The user will be presented with a menu where they can choose a disk
        and pick individual drivers to install.

/tmp/dd_net contains the list of URLs given by the user.
/tmp/dd_disk contains the list of disk devices given by the user.
/tmp/dd_interactive contains "menu" if interactive mode was requested.

/tmp/dd.done should be created when all the user-requested stuff above has been
handled; the installer won't start up until this file is created.

Repositories for installed drivers are copied into /run/install/DD-X where X
starts at 1 and increments for each repository.

Selected driver package names are saved in /run/install/dd_packages.

Anaconda uses the repository and package list to install the same set of drivers
to the target system.
"""

import logging
import sys
import os
import subprocess
import fnmatch
import readline # pylint:disable=unused-import

from contextlib import contextmanager
from logging.handlers import SysLogHandler

# py2 compat
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open("/dev/null", 'a+')
try:
    _input = raw_input # pylint: disable=undefined-variable
except NameError:
    _input = input

log = logging.getLogger("DD")

arch = os.uname()[4]
kernelver = os.uname()[2]

def mkdir_seq(stem):
    """
    Create sequentially-numbered directories starting with stem.

    For example, mkdir_seq("/tmp/DD-") would create "/tmp/DD-1";
    if that already exists, try "/tmp/DD-2", "/tmp/DD-3", and so on,
    until a directory is created.

    Returns the newly-created directory name.
    """
    n = 1
    while True:
        dirname = str(stem) + str(n)
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno != 17: raise
            n += 1
        else:
            return dirname

def find_repos(mnt):
    """find any valid driverdisk repos that exist under mnt."""
    dd_repos = []
    for root, dirs, files in os.walk(mnt, followlinks=True):
        repo = root+"/rpms/"+arch
        if "rhdd3" in files and "rpms" in dirs and os.path.isdir(repo):
            log.debug("found repo: %s", repo)
            dd_repos.append(repo)
    return dd_repos

# NOTE: it's unclear whether or not we're supposed to recurse subdirs looking
# for .iso files, but that seems like a bad idea if you mount some huge disk..
# So I've made a judgement call: we only load .iso files from the toplevel.
def find_isos(mnt):
    """find files named '.iso' at the top level of mnt."""
    return [mnt+'/'+f for f in os.listdir(mnt) if f.lower().endswith('.iso')]

class Driver(object):
    """Represents a single driver (rpm), as listed by dd_list"""
    def __init__(self, source="", name="", flags="", description="", repo=""):
        self.source = source
        self.name = name
        self.flags = flags
        self.description = description
        self.repo = repo

def dd_list(dd_path, anaconda_ver=None, kernel_ver=None):
    log.debug("dd_list: listing %s", dd_path)
    if not anaconda_ver:
        anaconda_ver = '19.0'
    if not kernel_ver:
        kernel_ver = kernelver
    cmd = ["dd_list", '-d', dd_path, '-k', kernel_ver, '-a', anaconda_ver]
    out = subprocess.check_output(cmd, stderr=DEVNULL)
    out = out.decode('utf-8')
    drivers = [Driver(*d.split('\n',3)) for d in out.split('\n---\n') if d]
    log.debug("dd_list: found drivers: %s", ' '.join(d.name for d in drivers))
    for d in drivers: d.repo = dd_path
    return drivers

def dd_extract(rpm_path, outdir, kernel_ver=None, flags='-blmf'):
    log.debug("dd_extract: extracting %s", rpm_path)
    if not kernel_ver:
        kernel_ver = kernelver
    cmd = ["dd_extract", flags, '-r', rpm_path, '-d', outdir, '-k', kernel_ver]
    subprocess.check_output(cmd, stderr=DEVNULL) # discard stdout

def mount(dev, mnt=None):
    """Mount the given dev at the mountpoint given by mnt."""
    # NOTE: dev may be a filesystem image - "-o loop" is not necessary anymore
    if not mnt:
        mnt = mkdir_seq("/media/DD-")
    cmd = ["mount", dev, mnt]
    log.debug("mounting %s at %s", dev, mnt)
    subprocess.check_call(cmd)
    return mnt

def umount(mnt):
    log.debug("unmounting %s", mnt)
    subprocess.call(["umount", mnt])

@contextmanager
def mounted(dev, mnt=None):
    mnt = mount(dev, mnt)
    try:
        yield mnt
    finally:
        umount(mnt)

module_updates_dir = '/lib/modules/%s/updates' % os.uname()[2]
firmware_updates_dir = '/lib/firmware/updates'

def iter_files(topdir, pattern=None):
    """iterator; yields full paths to files under topdir that match pattern."""
    for head, _, files in os.walk(topdir):
        for f in files:
            if pattern is None or fnmatch.fnmatch(f, pattern):
                yield os.path.join(head, f)

def ensure_dir(d):
    """make sure the given directory exists."""
    subprocess.check_call(["mkdir", "-p", d])

def move_files(files, destdir):
    """move files into destdir (iff they're not already under destdir)"""
    ensure_dir(destdir)
    for f in files:
        if f.startswith(destdir):
            continue
        subprocess.call(["mv", "-f", f, destdir])

def copy_files(files, destdir):
    """copy files into destdir (iff they're not already under destdir)"""
    ensure_dir(destdir)
    for f in files:
        if f.startswith(destdir):
            continue
        subprocess.call(["cp", "-a", f, destdir])

def append_line(filename, line):
    """simple helper to append a line to a file"""
    if not line.endswith("\n"):
        line += "\n"
    with open(filename, 'a') as outf:
        outf.write(line)

def read_lines(filename):
    try:
        return open(filename).read().splitlines()
    except IOError:
        return []

def save_repo(repo, target="/run/install"):
    """copy a repo to the place where the installer will look for it later."""
    newdir = mkdir_seq(os.path.join(target, "DD-"))
    log.debug("save_repo: copying %s to %s", repo, newdir)
    subprocess.call(["cp", "-arT", repo, newdir])
    return newdir

def extract_drivers(drivers=None, repos=None, outdir="/updates",
                    pkglist="/run/install/dd_packages"):
    """
    Extract drivers - either a user-selected driver list or full repos.

    drivers should be a list of Drivers to extract, or None.
    repos should be a list of repo paths to extract, or None.
    (If both are empty, nothing happens..)

    If any packages containing modules or firmware are extracted, also:
    * call save_repo for that package's repo
    * write the package name(s) to pkglist.

    Returns True if any package containing modules was extracted.
    """
    if not drivers:
        drivers = []
    if repos:
        drivers += [d for repo in repos for d in dd_list(repo)]

    save_repos = set()
    new_drivers = False

    ensure_dir(outdir)

    for driver in drivers:
        log.info("Extracting: %s", driver.name)
        dd_extract(driver.source, outdir)
        # Make sure we install modules/firmware into the target system
        if 'modules' in driver.flags or 'firmwares' in driver.flags:
            append_line(pkglist, driver.name)
            save_repos.add(driver.repo)
            new_drivers = True

    # save the repos containing those packages
    for repo in save_repos:
        save_repo(repo)

    return new_drivers

def grab_driver_files(outdir="/updates"):
    """
    copy any modules/firmware we just extracted into the running system.
    return a list of the names of any modules we just copied.
    """
    modules = list(iter_files(outdir+'/lib/modules',"*.ko*"))
    firmware = list(iter_files(outdir+'/lib/firmware'))
    copy_files(modules, module_updates_dir)
    copy_files(firmware, firmware_updates_dir)
    move_files(modules, outdir+module_updates_dir)
    move_files(firmware, outdir+firmware_updates_dir)
    return [os.path.basename(m).split('.ko')[0] for m in modules]

def load_drivers(modnames):
    """run depmod and try to modprobe all the given module names."""
    log.debug("load_drivers: %s", modnames)
    subprocess.call(["depmod", "-a"])
    subprocess.call(["modprobe", "-a"] + modnames)

def process_driver_disk(dev, interactive=False):
    try:
        _process_driver_disk(dev, interactive=interactive)
    except (subprocess.CalledProcessError, IOError) as e:
        log.error("ERROR: %s", e)

def _process_driver_disk(dev, interactive=False):
    """
    Main entry point for processing a single driver disk.
    Mount the device/image, find repos, and install drivers from those repos.

    If there are no repos, look for .iso files, and (if present) recursively
    process those.

    If interactive, ask the user which driver(s) to install from the repos,
    or ask which iso file to process (if no repos).
    """
    log.info("Examining %s", dev)
    with mounted(dev) as mnt:
        repos = find_repos(mnt)
        isos = find_isos(mnt)

        if repos:
            if interactive:
                new_modules = extract_drivers(drivers=repo_menu(repos))
            else:
                new_modules = extract_drivers(repos=repos)
            if new_modules:
                modules = grab_driver_files()
                load_drivers(modules)
        elif isos:
            if interactive:
                isos = iso_menu(isos)
            for iso in isos:
                process_driver_disk(iso, interactive=interactive)
        else:
            print("=== No driver disks found in %s! ===\n" % dev)

def mark_finished(user_request, topdir="/tmp"):
    log.debug("marking %s complete in %s", user_request, topdir)
    append_line(topdir+"/dd_finished", user_request)

def all_finished(topdir="/tmp"):
    finished = read_lines(topdir+"/dd_finished")
    todo = read_lines(topdir+"/dd_todo")
    return all(r in finished for r in todo)

def finish(user_request, topdir="/tmp"):
    # mark that we've finished processing this request
    mark_finished(user_request, topdir)
    # if we're done now, let dracut know
    if all_finished(topdir):
        append_line(topdir+"/dd.done", "true")

# --- DEVICE LISTING HELPERS FOR THE MENU -----------------------------------

class DeviceInfo(object):
    def __init__(self, **kwargs):
        self.device = kwargs.get("DEVNAME", '')
        self.uuid = kwargs.get("UUID", '')
        self.fs_type = kwargs.get("TYPE", '')
        self.label = kwargs.get("LABEL", '')

    def __repr__(self):
        return '<DeviceInfo %s>' % self.device

    @property
    def shortdev(self):
        if os.path.islink(self.device):
            return os.path.basename(os.readlink(self.device))
        elif self.device.startswith('/dev/'):
            return self.device[5:]
        else:
            return self.device

def blkid():
    out = subprocess.check_output("blkid -o export -s UUID -s TYPE".split())
    out = out.decode('ascii')
    return [dict(kv.split('=',1) for kv in block.splitlines())
                                 for block in out.split('\n\n')]

def get_disk_labels():
    return {os.path.realpath(s):os.path.basename(s)
            for s in iter_files("/dev/disk/by-label")}

def get_deviceinfo():
    disk_labels = get_disk_labels()
    deviceinfo = [DeviceInfo(**d) for d in blkid()]
    for dev in deviceinfo:
        dev.label = disk_labels.get(dev.device, '')
    return deviceinfo

# --- INTERACTIVE MENU JUNK ------------------------------------------------

class TextMenu(object):
    def __init__(self, items, title=None, formatter=None, headeritem=None,
                 refresher=None, multi=False, page_height=20):
        self.items = items
        self.title = title
        self.formatter = formatter
        self.headeritem = headeritem
        self.refresher = refresher
        self.multi = multi
        self.page_height = page_height
        self.pagenum = 1
        self.selected_items = []
        self.is_done = False
        if callable(items):
            self.refresher = items
            self.refresh()

    @property
    def num_pages(self):
        pages, leftover = divmod(len(self.items), self.page_height)
        if leftover:
            return pages+1
        else:
            return pages

    def next(self):
        if self.pagenum < self.num_pages:
            self.pagenum += 1

    def prev(self):
        if self.pagenum > 1:
            self.pagenum -= 1

    def refresh(self):
        if callable(self.refresher):
            self.items = self.refresher()

    def done(self):
        self.is_done = True

    def invalid(self, k):
        print("Invalid selection %r" % k)

    def toggle_item(self, item):
        if item in self.selected_items:
            self.selected_items.remove(item)
        else:
            self.selected_items.append(item)
        if not self.multi:
            self.done()

    def items_on_page(self):
        start_idx = (self.pagenum-1) * self.page_height
        if start_idx > len(self.items):
            return []
        else:
            items = self.items[start_idx:start_idx+self.page_height]
            return enumerate(items, start=start_idx)

    def format_item(self, item):
        if callable(self.formatter):
            return self.formatter(item)
        else:
            return str(item)

    def format_items(self):
        for n, i in self.items_on_page():
            if self.multi:
                x = 'x' if i in self.selected_items else ' '
                yield "%2d) [%s] %s" % (n+1, x, self.format_item(i))
            else:
                yield "%2d) %s" % (n+1, self.format_item(i))

    def format_header(self):
        if self.multi:
            return '        '+self.format_item(self.headeritem)
        else:
            return '    '+self.format_item(self.headeritem)

    def action_dict(self):
        actions = {
            'r': self.refresh,
            'n': self.next,
            'p': self.prev,
            'c': self.done,
        }
        for n, i in self.items_on_page():
            actions[str(n+1)] = lambda item=i: self.toggle_item(item)
        return actions

    def format_page(self):
        page = '\n(Page {pagenum} of {num_pages}) {title}\n{items}'
        items = list(self.format_items())
        if self.headeritem:
            items.insert(0, self.format_header())
        return page.format(pagenum=self.pagenum,
                           num_pages=self.num_pages,
                           title=self.title or '',
                           items='\n'.join(items))

    def format_prompt(self):
        options = [
            '# to toggle selection' if self.multi else '# to select',
            "'r'-refresh" if callable(self.refresher) else None,
            "'n'-next page" if self.pagenum < self.num_pages else None,
            "'p'-previous page" if self.pagenum > 1 else None,
            "or 'c'-continue"
        ]
        return ', '.join(o for o in options if o is not None) + ': '

    def run(self):
        while not self.is_done:
            print(self.format_page())
            k = _input(self.format_prompt())
            action = self.action_dict().get(k)
            if action:
                action()
            else:
                self.invalid(k)
        return self.selected_items

def repo_menu(repos):
    drivers = [d for r in repos for d in dd_list(r)]
    if not drivers:
        log.info("No suitable drivers found.")
        return []
    menu = TextMenu(drivers, title="Select drivers to install",
                             formatter=lambda d: d.source,
                             multi=True)
    result = menu.run()
    return result

def iso_menu(isos):
    menu = TextMenu(isos, title="Choose driver disk ISO file")
    result = menu.run()
    return result

def device_menu():
    fmt = '{0.shortdev:<8.8} {0.fs_type:<8.8} {0.label:<20.20} {0.uuid:<.36}'
    hdr = DeviceInfo(DEVNAME='DEVICE', TYPE='TYPE', LABEL='LABEL', UUID='UUID')
    menu = TextMenu(get_deviceinfo, title="Driver disk device selection",
                                    formatter=fmt.format,
                                    headeritem=hdr)
    result = menu.run()
    return result

# --- COMMANDLINE-TYPE STUFF ------------------------------------------------

def setup_log():
    log.setLevel(logging.DEBUG)
    handler = SysLogHandler(address="/dev/log")
    log.addHandler(handler)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("DD: %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)

def print_usage():
    print("usage: driver-updates --interactive")
    print("       driver-updates --disk DISK KERNELDEV")
    print("       driver-updates --net URL LOCALFILE")

def check_args(args):
    if args and args[0] == '--interactive':
        return True
    elif len(args) == 3 and args[0] in ('--disk', '--net'):
        return True
    else:
        return False

def main(args):
    if not check_args(args):
        print_usage()
        raise SystemExit(2)

    mode = args.pop(0)

    if mode in ('--disk', '--net'):
        request, dev = args
        process_driver_disk(dev)

    elif mode == '--interactive':
        log.info("starting interactive mode")
        request = 'menu'
        while True:
            dev = device_menu()
            if not dev: break
            process_driver_disk(dev.pop().device, interactive=True)

    finish(request)

if __name__ == '__main__':
    setup_log()
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        log.info("exiting.")
