#!/usr/bin/python3

import sys

from pocketlint import FalsePositive, PocketLintConfig, PocketLinter

class AnacondaLintConfig(PocketLintConfig):
    def __init__(self):
        PocketLintConfig.__init__(self)

        self.falsePositives = [ FalsePositive(r"^E0611.*: No name '_isys' in module 'pyanaconda'$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from BaseException: GError$"),
                                FalsePositive(r"^E0712.*: Catching an exception which doesn't inherit from BaseException: S390Error$"),

                                # XXX: These are temporary until dogtail and koji have python3 versions.
                                FalsePositive(r"^F0401.*: Unable to import 'dogtail.*'$"),
                                FalsePositive(r"^F0401.*: Unable to import 'koji'$")
                              ]

    @property
    def extraArgs(self):
        return ["--init-import", "y"]

    @property
    def initHook(self):
        return """'import gi.overrides, os; gi.overrides.__path__[0:0] = (os.environ["ANACONDA_WIDGETS_OVERRIDES"].split(":") if "ANACONDA_WIDGETS_OVERRIDES" in os.environ else [])'"""

if __name__ == "__main__":
    conf = AnacondaLintConfig()
    linter = PocketLinter(conf)
    rc = linter.run()
    sys.exit(rc)
