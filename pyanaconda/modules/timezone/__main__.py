import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.timezone.timezone import TimezoneModule

timezone_module = TimezoneModule()
timezone_module.run()
