from pyanaconda.modules.common import init
init()

from pyanaconda.modules.timezone.timezone import TimezoneModule
timezone_module = TimezoneModule()
timezone_module.run()
