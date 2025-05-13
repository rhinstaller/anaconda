#!/usr/bin/python3
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
"""
Driver Update Disk handler program.

This will be called once for each requested driverdisk (non-interactive), and
once for interactive mode (if requested).

Usage is one of:

    driver-updates --disk DISKSTR DEVNODE [RPMPATH]

        DISKSTR is the string passed by the user ('/dev/sda3', 'LABEL=DD', etc.)
        DEVNODE is the actual device node or image (/dev/sda3, /dev/sr0, etc.)
        RPMPATH is the path to the rpm file on the DEVNODE mountable device

        DEVNODE must be mountable, but need not actually be a block device
        (e.g. /dd.iso is valid if the user has inserted /dd.iso into initrd)

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

Packages will be extracted to /updates, which gets overlaid on top
of the installer's filesystem when we leave the initramfs.

Modules and firmware get moved to /lib/modules/`uname -r`/updates and
/lib/firmware/updates (under /updates, as above). They also get copied into the
corresponding paths in the initramfs, so we can load them immediately.

The repositories get copied into /run/install/DD-1, /run/install/DD-2, etc.
Driver package names are saved in /run/install/dd_packages.

During system installation, anaconda will install the packages listed in
/run/install/dd_packages to the target system.
"""

import fnmatch
import logging
import os
import subprocess
import sys

# Import readline so raw_input gets readline features, like history, and
# backspace working right. Do not import readline if not connected to a tty
# because it breaks sometimes.
if os.isatty(0):
    import readline  # pylint:disable=unused-import
import shutil
from contextlib import contextmanager
from logging.handlers import SysLogHandler

# py2 compat
try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open("/dev/null", 'a+')
try:
    _input = raw_input  # pylint: disable=undefined-variable
except NameError:
    _input = input

log = logging.getLogger("DD")

# NOTE: Yes, the version is wrong, but previous versions of this utility also
# hardcoded this value, because changing it will break any driver disk that has
# binary/library packages with "installer-enhancement = 19.0"..
# If we *need* to break compatibility, this should definitely get changed, but
# otherwise we probably shouldn't change this unless/until we're sure that
# everyone is using something like "installer-enhancement >= 19.0" instead..
ANACONDAVER = "19.0"

ARCH = os.uname()[4]
KERNELVER = os.uname()[2]

MODULE_UPDATES_DIR = "/lib/modules/%s/updates" % KERNELVER
FIRMWARE_UPDATES_DIR = "/lib/firmware/updates"


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
            if e.errno != 17:
                raise
            n += 1
        else:
            return dirname


def find_repos(mnt):
    """find any valid driverdisk repos that exist under mnt."""
    dd_repos = []
    for root, dirs, files in os.walk(mnt, followlinks=True):
        repo = root+"/rpms/"+ARCH
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
        anaconda_ver = ANACONDAVER
    if not kernel_ver:
        kernel_ver = KERNELVER
    cmd = ["dd_list", '-d', dd_path, '-k', kernel_ver, '-a', anaconda_ver]
    out = subprocess.check_output(cmd, stderr=DEVNULL, universal_newlines=True)
    drivers = [Driver(*d.split('\n', 3)) for d in out.split('\n---\n') if d]
    log.debug("dd_list: found drivers: %s", ' '.join(d.name for d in drivers))
    for d in drivers:
        d.repo = dd_path
    return drivers


def dd_extract(rpm_path, outdir, kernel_ver=None, flags='-blmf'):
    log.debug("dd_extract: extracting %s", rpm_path)
    if not kernel_ver:
        kernel_ver = KERNELVER
    cmd = ["dd_extract", flags, '-r', rpm_path, '-d', outdir, '-k', kernel_ver]
    subprocess.check_output(cmd, stderr=DEVNULL)  # discard stdout


def list_drivers(repos, anaconda_ver=None, kernel_ver=None):
    return [d for r in repos for d in dd_list(r, anaconda_ver, kernel_ver)]


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


def iter_files(topdir, pattern=None):
    """iterator; yields full paths to files under topdir that match pattern."""
    for head, _, files in os.walk(topdir):
        for f in files:
            if pattern is None or fnmatch.fnmatch(f, pattern):
                yield os.path.join(head, f)


def ensure_dir(d):
    """make sure the given directory exists."""
    subprocess.check_call(["mkdir", "-p", d])


def move_files(files, destdir, basedir):
    """move files into destdir (iff they're not already under destdir)"""
    for f in files:
        if f.startswith(destdir):
            continue
        dest = destdir+"/"+dest_strip(f, basedir)
        ensure_dir(os.path.dirname(dest))
        subprocess.call(["mv", "-f", f, dest])


def dest_strip(dest, basedir):
    """strip a base directory plus kernel version from a path"""
    # Strip the basedir and any leftover leading /'s
    dest = dest[len(basedir):]
    while dest.startswith('/'):
        dest = dest[1:]

    # Look for a leading directory that is a version number
    if "/" in dest and fnmatch.fnmatch(dest, "*.ko*") and dest[0].isdigit():
        # Drop the leading directory
        dest = "/".join(dest.split('/')[1:])

        if dest.startswith("kernel/"):
            dest = "/".join(dest.split('/')[1:])

    return dest


def copy_files(files, destdir, basedir):
    """copy files into destdir (iff they're not already under destdir)"""
    for f in files:
        if f.startswith(destdir):
            continue

        dest = destdir+"/"+dest_strip(f, basedir)
        ensure_dir(os.path.dirname(dest))
        subprocess.call(["cp", "-a", f, dest])


def append_line(filename, line):
    """simple helper to append a line to a file"""
    if not line.endswith("\n"):
        line += "\n"
    with open(filename, 'a') as outf:
        outf.write(line)
    log.debug("added line %s to file '%s'", f"{line!r}", filename)


# NOTE: items returned by read_lines should match items passed to append_line,
#       which is why we remove the newlines
def read_lines(filename):
    """return a list containing each line in filename, with newlines removed."""
    try:
        return [line.rstrip('\n') for line in open(filename)]
    except OSError:
        return []


def save_repo(repo, target="/run/install"):
    """copy a repo to the place where the installer will look for it later."""
    newdir = mkdir_seq(os.path.join(target, "DD-"))
    log.debug("save_repo: copying %s to %s", repo, newdir)
    # repo can be two sorts of stuff:
    # - a path to directory containing rpm files
    # -> in this case copy it's contents to target
    # - a path to an RPM file
    # -> in this case copy the file to destination
    if os.path.isfile(repo):
        shutil.copy2(repo, newdir)
    elif os.path.isdir(repo):
        for root, dirs, files in os.walk(repo):
            dest_path = os.path.join(newdir, os.path.relpath(root, repo))
            for file in files:
                item_path = os.path.join(repo, root, file)
                log.debug("copying %s to %s", item_path, dest_path)
                shutil.copy2(item_path, dest_path)
            for directory in dirs:
                item_path = os.path.join(dest_path, directory)
                log.debug("creating %s", item_path)
                os.mkdir(item_path)
    else:
        log.error("ERROR: DD repository needs to be a file or a directory: %s",
                  repo)
    return newdir


def extract_drivers(drivers=None, repos=None, outdir="/updates",
                    pkglist="/run/install/dd_packages"):
    """
    Extract drivers - either a user-selected driver list or full repos.

    drivers should be a list of Drivers to extract, or None.
    repos should be a list of repo paths to extract, or None.
    Raises ValueError if you pass both.

    If any packages containing modules or firmware are extracted, also:
    * call save_repo for that package's repo
    * write the package name(s) to pkglist.

    Returns True if any package containing modules was extracted.
    """
    if not drivers:
        drivers = []
    if drivers and repos:
        raise ValueError("extract_drivers: drivers or repos, not both")
    if repos:
        drivers = list_drivers(repos)

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


def list_aliases(module):
    """
    return a list of the aliases provided by a module file,
    parsed from modinfo.
    """
    cmd = ["modinfo", "-F", "alias", module]
    out = subprocess.check_output(cmd, universal_newlines=True)

    # Turn the output into a list, and add the module itself
    out = out.strip()
    if out:
        alias_list = out.split("\n")
    else:
        alias_list = []

    return alias_list + [module]


def grab_driver_files(outdir="/updates"):
    """
    copy any modules/firmware we just extracted into the running system.
    returns a dict: keys are module names, value are a list of aliases
    provided by the module.
    """
    modules = list(iter_files(outdir+'/lib/modules', "*.ko*"))
    firmware = list(iter_files(outdir+'/lib/firmware'))

    module_dict = {os.path.basename(m).split('.ko')[0]: list_aliases(m) for m in modules}

    copy_files(modules, MODULE_UPDATES_DIR, outdir+'/lib/modules')
    copy_files(firmware, FIRMWARE_UPDATES_DIR, outdir+'/lib/firmware')
    move_files(modules, outdir+MODULE_UPDATES_DIR, outdir+'/lib/modules')
    move_files(firmware, outdir+FIRMWARE_UPDATES_DIR, outdir+'/lib/firmware')

    return module_dict


def net_intfs_by_modules(mods):
    """get list of network interfaces which are depending on given kernel module"""
    ret = set()
    for mod in mods:
        out = subprocess.check_output(["find-net-intfs-by-driver", mod],
                                      universal_newlines=True)
        ret.update([line.strip() for line in out.split('\n') if line])

    log.debug("Found %s interfaces for %s mods", ret, mods)
    return ret


def list_net_intfs():
    """return set of all network interfaces from system"""
    return set(os.listdir("/sys/class/net"))


def rm_net_intfs_for_unload(mods):
    """clear dracut settings for interfaces which will be removed by
       driver removal

       return set of affected network interfaces
    """
    intfs_for_removal = net_intfs_by_modules(mods)
    for intf in intfs_for_removal:
        log.debug("Removing Dracut settings for interface %s before driver unload", intf)
        subprocess.check_call(["anaconda-ifdown", intf])

    return intfs_for_removal


def get_all_loaded_modules():
    """parse /proc/modules for all loaded kernel modules"""
    all_modules = []
    with open("/proc/modules", "r") as modules:
        for line in modules:
            module_name = line.split(" ")[0]
            all_modules.append(module_name)
    return all_modules


def load_drivers(moddict):
    """load all drivers based on given aliases. In case the drivers are
    already present in the kernel, replace them with the new ones.
    """
    # Step 1: try to unload everything that's being replaced
    # Using the current depmod data, resolve all the aliases to a module name,
    # and pass those names to modprobe -r.
    # modprobe can probably handle the aliases themselves, but this reduces this
    # list so we don't have to worry as much about what the maximum command line
    # length is.

    # save snapshot of currently installed modules
    all_modules_org = get_all_loaded_modules()
    unload_modules = set()
    for modname in moddict.keys():
        cmd = ["modprobe", "-R", modname]
        try:
            out = subprocess.check_output(cmd, stderr=DEVNULL, universal_newlines=True)
            log.debug("resolving alias '%s' to mod '%s'", modname, out)
            if out:
                unload_modules.update(out.strip().split('\n'))
        except subprocess.CalledProcessError:
            pass

    log.debug("unload drivers: %s", unload_modules)
    if unload_modules:
        net_intfs_unload = rm_net_intfs_for_unload(unload_modules)
        pre_remove_intfs = list_net_intfs()
        log.debug("removing old modules %s", unload_modules)
        subprocess.call(["modprobe", "-r"] + list(unload_modules))
        intfs_removed = pre_remove_intfs - list_net_intfs()
        log.debug("unloading modules removed these network interfaces: '%s'", intfs_removed)
        if intfs_removed != net_intfs_unload:
            log.error("ERROR: removed %s interfaces are not expected interfaces for removal %s",
                      intfs_removed, net_intfs_unload)

    # Step 2: Update the depmod data and try to load the new module list
    log.debug("updating depmod data")
    subprocess.call(["depmod", "-a"])

    log.debug("load_drivers: %s", list(moddict.keys()))
    if moddict:
        log.debug("inserting modules %s", list(moddict.keys()))
        subprocess.call(["modprobe", "-a"] + list(moddict.keys()))

    # get new snapshot of currently installed modules
    all_modules_new = get_all_loaded_modules()
    # compare snapshots and get modules removed from system due to dependencies
    modules_to_add = set(all_modules_org) - set(all_modules_new)

    # load all modules removed due to dependencies again
    if modules_to_add:
        log.debug("inserting back modules removed due to dependencies %s", list(modules_to_add))
        subprocess.call(["modprobe", "-a"] + list(modules_to_add))


# We *could* pass in "outdir" if we wanted to extract things somewhere else,
# but right now the only use case is running inside the initramfs, so..
def process_driver_disk(dev, interactive=False):
    try:
        return _process_driver_disk(dev, interactive=interactive)
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("ERROR: %s", e)
        return {}


def _process_driver_disk(dev, interactive=False):
    """
    Main entry point for processing a single driver disk.
    Mount the device/image, find repos, and install drivers from those repos.

    If there are no repos, look for .iso files, and (if present) recursively
    process those.

    If interactive, ask the user which driver(s) to install from the repos,
    or ask which iso file to process (if no repos).

    The return value is a dictionary with the new module names as keys, and
    the value for each is a list of aliases for the module (including the
    module itself).
    """
    log.info("Examining %s", dev)
    modules = {}
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
        elif isos:
            if interactive:
                isos = iso_menu(isos)
            for iso in isos:
                modules.update(process_driver_disk(iso, interactive=interactive))
        else:
            print("=== No driver disks found in %s! ===\n" % dev)

    return modules


def process_driver_rpm(rpm, dev=None):
    try:
        if dev:
            return _process_driver_rpm_from_device(rpm, dev)
        else:
            return _process_driver_rpm(rpm)
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("ERROR: %s", e)
        return {}


def _process_driver_rpm_from_device(rpm, dev):
    """
    Mount the DEVNODE and call _process_driver_rpm() with the correct
    path to the mount.
    """
    log.info("Mounting dev %s", dev)
    with mounted(dev) as mnt:
        return _process_driver_rpm(mnt + rpm)


def _process_driver_rpm(rpm):
    """
    Process a single driver rpm. Extract it, install it, and copy the
    rpm for Anaconda to install on the target system.
    """
    log.info("Examining %s", rpm)
    new_modules = extract_drivers(repos=[rpm])
    if new_modules:
        return grab_driver_files()
    else:
        return {}


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
        # resolve any symlinks (/dev/disk/by-label/OEMDRV -> /dev/sr0)
        dev = os.path.realpath(self.device)
        # NOTE: not os.path.basename 'cuz some devices legitimately have
        # a '/' in their name: /dev/cciss/c0d0, /dev/i2o/hda, etc.
        if dev.startswith('/dev/'):
            dev = dev[5:]
        return dev


def blkid():
    try:
        out = subprocess.check_output("blkid -o export -s UUID -s TYPE".split(),
                                      universal_newlines=True)
        return [dict(kv.split('=', 1) for kv in block.splitlines())
                                      for block in out.split('\n\n')]
    except subprocess.CalledProcessError:
        return []


# We use this to get disk labels because blkid's encoding of non-printable and
# non-ascii characters is weird and doesn't match what you'd expect to see.
def get_disk_labels():
    return {os.path.realpath(s): os.path.basename(s)
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
            return (8*' ')+self.format_item(self.headeritem)
        else:
            return (4*' ')+self.format_item(self.headeritem)

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
    drivers = list_drivers(repos)
    if not drivers:
        log.info("No suitable drivers found.")
        return []
    menu = TextMenu(drivers,
                    title="Select drivers to install",
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
    menu = TextMenu(get_deviceinfo,
                    title="Driver disk device selection",
                    formatter=fmt.format,
                    headeritem=hdr)
    result = menu.run()
    return result

# --- COMMANDLINE-TYPE STUFF ------------------------------------------------


def setup_log():
    log.setLevel(logging.DEBUG)

    _set_console_logging()
    _set_syslog_logging()


def _set_console_logging():
    handler = logging.StreamHandler()
    # print debug messages into console only if debugging mode is enabled
    if is_debug_mode_enabled("/proc/cmdline"):
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)

    log.addHandler(handler)


def _set_syslog_logging():
    # all messages should always go to the syslog
    handler = SysLogHandler(address="/dev/log")
    handler.setLevel(logging.DEBUG)

    # log also message level to the syslog
    formatter = logging.Formatter("DD (%(levelname)s): %(message)s")
    handler.setFormatter(formatter)

    log.addHandler(handler)


def is_debug_mode_enabled(cmdline_path):
    """Detect enabled debugging mode.

    Debugging mode can be enabled by adding inst.debug or rd.debug on the kernel command line.

    :param cmdline_path: path to the cmdline file (should be /proc/cmdline)
    """
    with open(cmdline_path, 'rt') as f:
        content = f.readlines()

    for line in content:
        # remove white space characters from the end of file
        line = line.strip()
        for param in line.split(" "):
            key = param.split("=")[0]
            if key in ("inst.debug", "rd.debug"):
                return True

    return False


def print_usage():
    print("usage: driver-updates --interactive")
    print("       driver-updates --disk DISK KERNELDEV [RPMPATH]")
    print("       driver-updates --net URL LOCALFILE")


def check_args(args):
    if args and args[0] == '--interactive':
        return True
    elif len(args) == 3 and args[0] in ('--disk', '--net'):
        return True
    elif len(args) == 4 and args[0] == '--disk':
        return True
    else:
        return False


def main(args):
    if not check_args(args):
        print_usage()
        raise SystemExit(2)

    mode = args.pop(0)

    update_drivers = {}
    path = None
    if mode in ('--disk', '--net'):
        if len(args) == 3:
            request, dev, path = args
        else:
            request, dev = args

        log.debug("Processing: %s with dev %s", request, dev)

        # Guess whether this is an ISO or RPM based on the filename.
        # If neither matches, assume it is a device node and processes as an ISO.
        # This is relevant for both --disk and --net since --disk could be
        # pointing to files within the initramfs.
        if dev.endswith(".iso"):
            update_drivers.update(process_driver_disk(dev))
        elif dev.endswith(".rpm"):
            update_drivers.update(process_driver_rpm(dev))
        elif path:
            update_drivers.update(process_driver_rpm(path, dev))
        else:
            update_drivers.update(process_driver_disk(dev))

    elif mode == '--interactive':
        log.info("starting interactive mode")
        request = 'menu'
        while True:
            dev = device_menu()
            if not dev:
                break
            update_drivers.update(process_driver_disk(dev.pop().device, interactive=True))

    load_drivers(update_drivers)

    finish(request)

    # When using inst.dd and a cdrom stage2 it isn't mounted before running driver-updates
    # In order to get the stage2 cdrom mounted it either needs to be swapped back in
    # or we need to re-trigger the block rules.
    if os.path.exists("/tmp/anaconda-dd-on-cdrom") and not os.path.exists("/dev/root"):
        cmd = ["udevadm", "trigger", "--action=change", "--subsystem-match=block"]
        log.debug("triggering udevadm to mount cdrom with stage2 image")
        subprocess.check_call(cmd)


if __name__ == '__main__':
    setup_log()
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        log.debug("exiting.")

    log.debug("leaving the driver_updates script")
