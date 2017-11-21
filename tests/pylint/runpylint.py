#!/usr/bin/python3

import sys

from pocketlint import FalsePositive, PocketLintConfig, PocketLinter

class AnacondaLintConfig(PocketLintConfig):
    def __init__(self):
        PocketLintConfig.__init__(self)

        self.falsePositives = [ FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: GError$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: S390Error$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from (Base|)Exception: BlockDevError$"),

                                # TODO: Should be fixed with https://github.com/PyCQA/astroid/pull/433
                                FalsePositive(r"^E1129.*: Context manager 'lock' doesn't implement __enter__ and __exit__.$"),

                                # XXX: This is temporary until koji has python3 versions.
                                FalsePositive(r"^E0401.*: Unable to import 'koji'$"),
                                FalsePositive(r"^E1101.*: Instance of 'GError' has no 'message' member"),
                                FalsePositive(r"^E1101.*: FedoraGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
                                FalsePositive(r"^E1101.*: HostipGeoIPProvider._refresh: Instance of 'LookupDict' has no 'ok' member"),
                                FalsePositive(r"^E1101.*: Geocoder._reverse_geocode_nominatim: Instance of 'LookupDict' has no 'ok' member"),
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

if __name__ == "__main__":
    conf = AnacondaLintConfig()
    linter = PocketLinter(conf)
    rc = linter.run()
    sys.exit(rc)
