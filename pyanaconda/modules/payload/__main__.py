from pyanaconda.modules.common import init
init()

from pyanaconda.modules.payload.payload import PayloadModule
payload_module = PayloadModule()
payload_module.run()
