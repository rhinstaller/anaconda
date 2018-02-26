import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.boss.boss import Boss

# instantiate the Boss class
boss = Boss()
# and start it
boss.run()

