from pyanaconda.modules.common import init
init()

from pyanaconda.modules.subscription.subscription import SubscriptionModule
subscription_module = SubscriptionModule()
subscription_module.run()
