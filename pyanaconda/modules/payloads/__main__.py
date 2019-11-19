from pyanaconda.modules.common import init
init()

from pyanaconda.modules.payloads.payloads import PayloadsService
service = PayloadsService()
service.run()
