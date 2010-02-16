import logging
import anaconda_log
import inspect

def log_method_call(d, *args, **kwargs):
    classname = d.__class__.__name__
    stack = inspect.stack()
    methodname = stack[1][3]

    spaces = len(stack) * ' '
    fmt = "%s%s.%s:"
    fmt_args = [spaces, classname, methodname]

    for arg in args:
        fmt += " %s ;"
        fmt_args.append(arg)

    for k, v in kwargs.items():
        fmt += " %s: %s ;"
        fmt_args.extend([k, v])

    logger.debug(fmt % tuple(fmt_args))


logger = logging.getLogger("storage")
logger.setLevel(logging.DEBUG)
anaconda_log.logger.addFileHandler("/tmp/storage.log", logger, logging.DEBUG)
anaconda_log.logger.addFileHandler("/dev/tty3", logger,
                                   anaconda_log.DEFAULT_TTY_LEVEL,
                                   anaconda_log.TTY_FORMAT,
                                   autoLevel=True)
anaconda_log.logger.forwardToSyslog(logger)
