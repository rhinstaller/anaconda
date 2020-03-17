from pyanaconda.modules.common import init
init("/tmp/storage.log")

from pyanaconda.modules.storage.storage import StorageService
service = StorageService()
service.run()
