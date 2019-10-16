from pyanaconda.modules.common import init
init()

from pyanaconda.modules.timezone.timezone import TimezoneService
service = TimezoneService()
service.run()
