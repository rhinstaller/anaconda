import os
import selinux
import subprocess

from size import Size

import logging
log = logging.getLogger("storage")
program_log = logging.getLogger("program")

def _run_program(argv, root='/', stdin=None, env_prune=None):
    if env_prune is None:
        env_prune = []

    def chroot():
        if root and root != '/':
            os.chroot(root)

    program_log.info("Running... %s" % argv)

    env = os.environ.copy()
    env.update({"LC_ALL": "C",
                "INSTALL_PATH": root})
    for var in env_prune:
        env.pop(var, None)

    try:
        proc = subprocess.Popen(argv,
                                stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                preexec_fn=chroot, cwd=root, env=env)

        while True:
            out = proc.communicate()[0]
            if out:
                for line in out.splitlines():
                    program_log.info(line)

            if proc.returncode is not None:
                break
    except OSError as e:
        program_log.error("Error running %s: %s" % (argv[0], e.strerror))
        raise

    program_log.debug("Return code: %d" % proc.returncode)
    return (proc.returncode, out)

def run_program(*args, **kwargs):
    return _run_program(*args, **kwargs)[0]

def capture_output(*args, **kwargs):
    return _run_program(*args, **kwargs)[1]

def mount(device, mountpoint, fstype, options=None):
    if options is None:
        options = "defaults"

    mountpoint = os.path.normpath(mountpoint)
    if not os.path.exists(mountpoint):
        makedirs(mountpoint)

    argv = ["mount", "-t", fstype, "-o", options, device, mountpoint]
    try:
        rc = run_program(argv)
    except OSError as e:
        raise

    return rc

def umount(mountpoint):
    try:
        rc = run_program(["umount", mountpoint])
    except OSError as e:
        raise

    return rc

def total_memory():
    """ Return the amount of system RAM in kilobytes. """
    lines = open("/proc/meminfo").readlines()
    for line in lines:
        if line.startswith("MemTotal:"):
            mem = long(line.split()[1])

    return mem

##
## sysfs functions
##
def notify_kernel(path, action="change"):
    """ Signal the kernel that the specified device has changed.

        Exceptions raised: ValueError, IOError
    """
    log.debug("notifying kernel of '%s' event on device %s" % (action, path))
    path = os.path.join(path, "uevent")
    if not path.startswith("/sys/") or not os.access(path, os.W_OK):
        log.debug("sysfs path '%s' invalid" % path)
        raise ValueError("invalid sysfs path")

    f = open(path, "a")
    f.write("%s\n" % action)
    f.close()

def get_sysfs_attr(path, attr):
    if not attr:
        log.debug("get_sysfs_attr() called with attr=None")
        return None

    attribute = "/sys%s/%s" % (path, attr)
    attribute = os.path.realpath(attribute)

    if not os.path.isfile(attribute) and not os.path.islink(attribute):
        log.warning("%s is not a valid attribute" % (attr,))
        return None

    return open(attribute, "r").read().strip()

def get_sysfs_path_by_name(dev_node, class_name="block"):
    """ Return sysfs path for a given device.

        For a device node (e.g. /dev/vda2) get the respective sysfs path
        (e.g. /sys/class/block/vda2). This also has to work for device nodes
        that are in a subdirectory of /dev like '/dev/cciss/c0d0p1'.
     """
    dev_name = os.path.basename(dev_node)
    if dev_node.startswith("/dev/"):
        dev_name = dev_node[5:].replace("/", "!")
    sysfs_class_dir = "/sys/class/%s" % class_name
    dev_path = os.path.join(sysfs_class_dir, dev_name)
    if os.path.exists(dev_path):
        return dev_path
    else:
        raise RuntimeError("get_sysfs_path_by_name: Could not find sysfs path "
                           "for '%s' (it is not at '%s')" % (dev_node, dev_path))

##
## SELinux functions
##
def match_path_context(path):
    """ Return the default SELinux context for the given path. """
    context = None
    try:
        context = selinux.matchpathcon(os.path.normpath(path), 0)[1]
    except OSError as e:
        log.info("failed to get default SELinux context for %s: %s" % (path, e))

    return context

def set_file_context(path, context, root=None):
    """ Set the SELinux file context of a file.

        Arguments:

            path        filename string
            context     context string

        Keyword Arguments:

            root        an optional chroot string

        Return Value:

            True if successful, False if not.
    """
    if root is None:
        root = '/'

    full_path = os.path.normpath("%s/%s" % (root, path))
    if context is None or not os.access(full_path, os.F_OK):
        return False

    try:
        rc = (selinux.lsetfilecon(full_path, context) == 0)
    except OSError as e:
        log.info("failed to set SELinux context for %s: %s" % (full_path, e))
        rc = False

    return rc

def reset_file_context(path, root=None):
    """ Restore the SELinux context of a file to its default value.

        Arguments:

            path        filename string

        Keyword Arguments:

            root        an optional chroot string

        Return Value:

            If successful, returns the file's new/default context.
    """
    context = match_path_context(path)
    if context:
        if set_file_context(path, context, root=root):
            return context

##
## Miscellaneous
##
def find_program_in_path(prog, raise_on_error=False):
    for d in os.environ["PATH"].split(os.pathsep):
        full = os.path.join(d, prog)
        if os.access(full, os.X_OK):
            return full

    if raise_on_error:
        raise RuntimeError("Unable to locate a needed executable: '%s'" % prog)

def makedirs(path):
    if not os.path.isdir(path):
        os.makedirs(path, 0755)

def copy_to_system(source):
    if not os.access(source, os.R_OK):
        log.info("copy_to_system: source '%s' does not exist." % source)
        return False

    target = ROOT_PATH + source
    target_dir = os.path.dirname(target)
    log.debug("copy_to_system: '%s' -> '%s'." % (source, target))
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    shutil.copy(source, target)
    return True

def lsmod():
    """ Returns list of names of all loaded modules. """
    with open("/proc/modules") as f:
        lines = f.readlines()
    return [l.split()[0] for l in lines]

def get_option_value(opt_name, options):
    """ Return the value of a named option in the specified options string. """
    for opt in options.split(","):
        if "=" not in opt:
            continue

        name, val = opt.split("=")
        if name == opt_name:
            return val.strip()

def numeric_type(num):
    """ Verify that a value is given as a numeric data type.

        Return the number if the type is sensible or raise ValueError
        if not.
    """
    if num is None:
        num = 0
    elif not (isinstance(num, int) or \
              isinstance(num, long) or \
              isinstance(num, float)):
        raise ValueError("value (%s) must be either a number or None" % num)

    return num

def insert_colons(a_string):
    """ Insert colon between every second character.

        E.g. creates 'al:go:ri:th:ms' from 'algoritms'. Useful for formatting
        MAC addresses and wwids for output.
    """
    suffix = a_string[-2:]
    if len(a_string) > 2:
        return insert_colons(a_string[:-2]) + ':' + suffix
    else:
        return suffix
