from pyanaconda.modules.common import init
init()

from pyanaconda.modules.security.security import SecurityService
service = SecurityService()
service.run()
