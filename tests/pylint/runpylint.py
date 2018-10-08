#!/usr/bin/python3

import sys
import time

from os import path
from pocketlint import FalsePositive, PocketLintConfig, PocketLinter

TIME_LOG = "pylint-time.log"


class AnacondaLintConfig(PocketLintConfig):
    def __init__(self):
        PocketLintConfig.__init__(self)

        self.falsePositives = [ FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: GError$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: S390Error$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: BlockDevError$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: Swap*Error$"),
                                FalsePositive(r"^E1101.*: Instance of 'KickstartSpecificationHandler' has no '.*' member$"),
                                FalsePositive(r"^E1101.*: Method 'PropertiesChanged' has no 'connect' member$"),
                                FalsePositive(r"^E1101.*: Instance of 'GError' has no 'message' member"),
                                FalsePositive(r"^E1101.*: FedoraGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
                                FalsePositive(r"^E1101.*: HostipGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
                                FalsePositive(r"^E1101.*: Geocoder._reverse_geocode_nominatim: Instance of 'LookupDict' has no 'ok' member"),
                                FalsePositive(r"^E1101.*: Instance of 'Namespace' has no '.*' member$"),
                                FalsePositive(r"^E1101.*: Module 'crypt' has no 'METHOD_MD5' member$"),
                                FalsePositive(r"^E1101.*: Module 'crypt' has no 'METHOD_SHA256' member$"),
                                FalsePositive(r"^E1101.*: Module 'crypt' has no 'METHOD_SHA512' member$"),

                                # TODO: BlockDev introspection needs to be added to pylint to handle these
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_needs_format' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_format' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'sanitize_dev_input' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_online' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_wwpn_input' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'zfcp_sanitize_lun_input' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'name_from_node' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'generate_backup_passphrase' member"),
                                FalsePositive(r"E1101.*: Instance of 'int' has no 'dasd_is_ldl' member"),
                              ]

    @property
    def extraArgs(self):
        return ["--init-import", "y"]

    @property
    def initHook(self):
        return """'import gi.overrides, os; gi.overrides.__path__[0:0] = (os.environ["ANACONDA_WIDGETS_OVERRIDES"].split(":") if "ANACONDA_WIDGETS_OVERRIDES" in os.environ else [])'"""

    @property
    def ignoreNames(self):
        return {"translation-canary"}


def _get_timelog_path():
    log_dir = path.dirname(path.realpath(__file__))
    return "{}/{}".format(log_dir, TIME_LOG)


def save_start_time():
    lt = time.localtime()
    with open(_get_timelog_path(), 'at') as f:
        f.write("Start - {}:{}:{}\n".format(lt.tm_hour, lt.tm_min, lt.tm_sec))


def save_end_time():
    lt = time.localtime()
    with open(_get_timelog_path(), 'at') as f:
        f.write("End - {}:{}:{}\n".format(lt.tm_hour, lt.tm_min, lt.tm_sec))


if __name__ == "__main__":
    conf = AnacondaLintConfig()
    linter = PocketLinter(conf)
    save_start_time()
    rc = linter.run()
    save_end_time()
    sys.exit(rc)
