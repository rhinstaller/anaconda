import inspect
import logging

log = logging.getLogger("storage")
log.addHandler(logging.NullHandler())

def function_name_and_depth():
    IGNORED_FUNCS = ["function_name_and_depth",
                     "log_method_call",
                     "log_method_return"]
    stack = inspect.stack()

    for i, frame in enumerate(stack):
        methodname = frame[3]
        if methodname not in IGNORED_FUNCS:
            return (methodname, len(stack) - i)

    return ("unknown function?", 0)

def log_method_call(d, *args, **kwargs):
    classname = d.__class__.__name__
    (methodname, depth) = function_name_and_depth()
    spaces = depth * ' '
    fmt = "%s%s.%s:"
    fmt_args = [spaces, classname, methodname]

    for arg in args:
        fmt += " %s ;"
        fmt_args.append(arg)

    for k, v in kwargs.items():
        fmt += " %s: %s ;"
        if "pass" in k.lower() and v:
            v = "Skipped"
        fmt_args.extend([k, v])

    logging.getLogger("storage").debug(fmt % tuple(fmt_args))

def log_method_return(d, retval):
    classname = d.__class__.__name__
    (methodname, depth) = function_name_and_depth()
    spaces = depth * ' '
    fmt = "%s%s.%s returned %s"
    fmt_args = (spaces, classname, methodname, retval)
    logging.getLogger("storage").debug(fmt % fmt_args)

