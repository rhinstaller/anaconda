import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.bar.bar import Bar

bar = Bar()
bar.run()
