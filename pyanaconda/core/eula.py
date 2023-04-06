import os
from pyanaconda.core.configuration.anaconda import conf

def get_license_file_name():
    """Get filename of the license file best matching current localization settings.

    :return: filename of the license file or None if no license file found
    :rtype: str or None
    """
    if not conf.license.eula:
        return None

    if not os.path.exists(conf.license.eula):
        return None

    return conf.license.eula


def eula_available():
    """Report if it looks like there is an EULA available on the system.

    :return: True if an EULA seems to be available, False otherwise
    :rtype: bool
    """
    return bool(get_license_file_name())
