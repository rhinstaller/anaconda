import os
import pydbus

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

def get_bus():
    """Get a DBUS bus connection corresponding to the current environment.

    During normal usage this function should return connection to the system bus,
    but during testing/development a custom bus might be used.
    So just always connect to the bus specified by the DBUS_STARTER_ADDRESS
    environmental variable.
    """
    bus_address = os.environ.get("DBUS_STARTER_ADDRESS")
    if bus_address:
        return pydbus.connect(os.environ["DBUS_STARTER_ADDRESS"])
    else:
        log.critical("DBUS_STARTER_ADDRESS not defined, can't use DBUS!")
        raise RuntimeError("DBUS_STARTER_ADDRESS not defined in environment")

