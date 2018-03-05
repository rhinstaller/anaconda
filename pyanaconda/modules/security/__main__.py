import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.security.security import SecurityModule

security_module = SecurityModule()
security_module.run()
