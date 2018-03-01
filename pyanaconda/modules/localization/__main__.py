import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.localization.localization import LocalizationModule

localization_module = LocalizationModule()
localization_module.run()
