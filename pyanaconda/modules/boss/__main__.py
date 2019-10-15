from pyanaconda.modules.common import init
init()

from pyanaconda.modules.boss.boss import Boss
service = Boss()
service.run()
