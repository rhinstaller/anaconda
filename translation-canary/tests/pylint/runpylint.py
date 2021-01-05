#!/usr/bin/env python3

import sys
from pocketlint import PocketLintConfig, PocketLinter

class TranslationCanaryLintConfig(PocketLintConfig):
    @property
    def disabledOptions(self):
        return [ "I0011",           # Locally disabling %s
               ]

    @property
    def extraArgs(self):
        return ["--init-import", "y"]

if __name__ == "__main__":
    conf = TranslationCanaryLintConfig()
    linter = PocketLinter(conf)
    rc = linter.run()
    sys.exit(rc)
