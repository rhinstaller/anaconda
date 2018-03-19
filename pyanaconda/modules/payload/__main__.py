import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.payload.payload import PayloadModule

payload_module = PayloadModule()
payload_module.run()
