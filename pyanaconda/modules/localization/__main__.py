from pyanaconda.modules.common import init
init()

from pyanaconda.modules.localization.localization import LocalizationService
service = LocalizationService()
service.run()
