from pyanaconda.modules.common import init
init()

from pyanaconda.modules.localization.localization import LocalizationModule
localization_module = LocalizationModule()
localization_module.run()
