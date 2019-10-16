from pyanaconda.modules.common import init
init()

from pyanaconda.modules.services.services import ServicesService
service = ServicesService()
service.run()
