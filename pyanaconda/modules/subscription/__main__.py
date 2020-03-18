from pyanaconda.modules.common import init
init()

from pyanaconda.modules.subscription.subscription import SubscriptionService
service = SubscriptionService()
service.run()
