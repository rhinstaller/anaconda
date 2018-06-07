from pyanaconda.modules.common import init
init()

from pyanaconda.modules.users.users import UsersModule
users_module = UsersModule()
users_module.run()
