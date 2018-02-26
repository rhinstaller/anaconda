import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.foo.foo import Foo

foo = Foo()
foo.run()
