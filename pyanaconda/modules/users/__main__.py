from pyanaconda.modules.common import init
init()

from pyanaconda.modules.users.users import UsersService
service = UsersService()
service.run()
