from pyanaconda.modules.common import init
init()

from pyanaconda.modules.boss.boss import Boss
boss = Boss()
boss.run()
