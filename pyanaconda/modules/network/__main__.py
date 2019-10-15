from pyanaconda.modules.common import init
init()

from pyanaconda.modules.network.network import NetworkService
service = NetworkService()
service.run()
