import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.storage.storage import StorageModule

storage_module = StorageModule()
storage_module.run()
