import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.users.users import UsersModule

users_module = UsersModule()
users_module.run()
