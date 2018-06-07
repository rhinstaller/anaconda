from pyanaconda.modules.common import init
init()

from pyanaconda.dbus_addons.baz.baz import Baz
baz = Baz()
baz.run()
