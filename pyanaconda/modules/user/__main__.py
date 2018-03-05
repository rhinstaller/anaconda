import logging
logging.basicConfig(level=logging.DEBUG)

from pyanaconda.modules.user.user import UserModule

user_module = UserModule()
user_module.run()
