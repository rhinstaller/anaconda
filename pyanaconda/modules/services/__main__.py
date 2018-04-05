import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.services.services import ServicesModule

services_module = ServicesModule()
services_module.run()
