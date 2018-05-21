from pyanaconda.modules.common import init
init()

from pyanaconda.modules.services.services import ServicesModule
services_module = ServicesModule()
services_module.run()
