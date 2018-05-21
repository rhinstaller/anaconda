from pyanaconda.modules.common import init
init()

from pyanaconda.modules.network.network import NetworkModule
network_module = NetworkModule()
network_module.run()
