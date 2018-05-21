from pyanaconda.modules.common import init
init()

from pyanaconda.modules.storage.storage import StorageModule
storage_module = StorageModule()
storage_module.run()
