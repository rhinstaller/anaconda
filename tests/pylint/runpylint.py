#!/usr/bin/python3

import os

from pocketlint import FalsePositive, PocketLintConfig, PocketLinter

class AnacondaLintConfig(PocketLintConfig):
    def __init__(self):
        self.falsePositives = [ FalsePositive(r"^E1101:[ 0-9]*,[0-9]*:.*: Instance of '.*' has no 'get_property' member$"),
                                FalsePositive(r"^E1101:[ 0-9]*,[0-9]*:.*: Instance of '.*' has no 'set_property' member$"),
                                FalsePositive(r"^E0611:[ 0-9]*,[0-9]*: No name '_isys' in module 'pyanaconda'$"),
                                FalsePositive(r"^E0611:[ 0-9]*,[0-9]*:.*: No name '_isys' in module 'pyanaconda'$"),
                                FalsePositive(r"^E0712:[ 0-9]*,[0-9]*:.*: Catching an exception which doesn't inherit from BaseException: GError$"),
                                FalsePositive(r"gi/module.py:[0-9]*: Warning: g_hash_table_insert_internal: assertion 'hash_table != NULL' failed$"),
                                FalsePositive(r"^  g_type = info\.get_g_type\(\)$")
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
    os._exit(rc)
