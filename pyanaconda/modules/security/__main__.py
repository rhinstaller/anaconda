from pyanaconda.modules.common import init
init()

from pyanaconda.modules.security.security import SecurityModule
security_module = SecurityModule()
security_module.run()
