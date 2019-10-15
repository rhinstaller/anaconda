from pyanaconda.modules.common import init
init()

from pyanaconda.modules.storage.storage import StorageService
service = StorageService()
service.run()
