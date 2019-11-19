from pyanaconda.modules.common import init
init()

from pyanaconda.modules.payloads.payload import PayloadService
service = PayloadService()
service.run()
