# iutil.py stubs
import os

import logging
log = logging.getLogger("storage")

def notify_kernel(path, action="change"):
    """ Signal the kernel that the specified device has changed. """
    log.debug("notifying kernel of '%s' event on device %s" % (action, path))
    path = os.path.join(path, "uevent")
    if not path.startswith("/sys/") or not os.access(path, os.W_OK):
        log.debug("sysfs path '%s' invalid" % path)
        raise ValueError("invalid sysfs path")

    f = open(path, "a")
    f.write("%s\n" % action)
    f.close()

def get_sysfs_path_by_name(dev_name, class_name="block"):
    dev_name = os.path.basename(dev_name)
    sysfs_class_dir = "/sys/class/%s" % class_name
    dev_path = os.path.join(sysfs_class_dir, dev_name)
    if os.path.exists(dev_path):
        return dev_path

import inspect
def log_method_call(d, *args, **kwargs):
    classname = d.__class__.__name__
    methodname = inspect.stack()[1][3]
    fmt = "%s.%s:"
    fmt_args = [classname, methodname]
    for arg in args:
        fmt += " %s ;"
        fmt_args.append(arg)

    for k, v in kwargs.items():
        fmt += " %s: %s ;"
        fmt_args.extend([k, v])

    log.debug(fmt % tuple(fmt_args))

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


