from pyanaconda.modules.common import init
init()

from pyanaconda.modules.payload.payload import PayloadService
service = PayloadService()
service.run()
