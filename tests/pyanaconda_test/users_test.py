#!/usr/bin/python

import mock
import sys

GIDNUMBER = 'pw_gid'
HOMEDIRECTORY = 'pw_dir'

class UsersTest(mock.TestCase):
    def setUp(self):
        self.setupModules(["_isys", "block", "ConfigParser"])
        
        self.fs = mock.DiskIO()
        self.anaconda = mock.Mock()
        self.anaconda.security.auth.find.return_value = -1
        
        import pyanaconda.users 
        pyanaconda.users.log = mock.Mock()
        pyanaconda.users.iutil = mock.Mock()
        pyanaconda.users.iutil.mkdirChain = mock.Mock()
        
        pyanaconda.users.os = mock.Mock()
        pyanaconda.users.os.fork.return_value=False
        pyanaconda.users.os.waitpid.return_value=(1, 1)
        pyanaconda.users.os.WEXITSTATUS.return_value=0
        
        pyanaconda.users.libuser.admin = mock.Mock()
        pyanaconda.users.libuser.GIDNUMBER = GIDNUMBER
        pyanaconda.users.libuser.HOMEDIRECTORY = HOMEDIRECTORY        
        pyanaconda.users.libuser.admin().lookupGroupByName.return_value = False        
        pyanaconda.users.libuser.admin().lookupUserByName.return_value = False
        pyanaconda.users.libuser.admin().initGroup().get.return_value = ['']
        pyanaconda.users.libuser.admin().initGroup().reset_mock()
        pyanaconda.users.libuser.admin().reset_mock()
    
    def tearDown(self):
        self.tearDownModules()
    
    def create_group_test(self):
        import pyanaconda.users     
 
        GROUP = 'Group'
        GID = 100
 
        usr = pyanaconda.users.Users(self.anaconda)
        self.assertTrue(usr.createGroup(GROUP, GID, root=''))
      
        methods = pyanaconda.users.libuser.admin().method_calls[:]
        try:
            if methods[2][0] == 'addGroup':
                methods.pop()
        except:
            pass
           
        self.assertEqual(methods,        
            [('lookupGroupByName', (GROUP,), {}), ('initGroup', (GROUP,), {}),])
        
        self.assertEqual(
            pyanaconda.users.libuser.admin().initGroup().method_calls,
            [('set', (GIDNUMBER, GID), {})])
        
    def create_user_test(self):
        import pyanaconda.users     
 
        USER = 'TestUser'
        PASS = 'abcde'
 
        usr = pyanaconda.users.Users(self.anaconda)
        self.assertTrue(usr.createUser(USER, PASS, root=''))
  
        self.assertTrue(pyanaconda.users.iutil.mkdirChain.called)
        
        methods = [x[0] for x in pyanaconda.users.libuser.admin().method_calls]
        self.assertEqual(methods, 
            ['lookupUserByName', 'initUser', 'initGroup', 'addUser','addGroup',
             'setpassUser', 'lookupGroupByName'])
        
        self.assertEqual(pyanaconda.users.libuser.admin().initUser.call_args_list,
            [((USER,), {})])
            
        self.assertEqual(pyanaconda.users.libuser.admin().initGroup.call_args_list,
            [((USER,), {})])
        
        self.assertEqual(pyanaconda.users.libuser.admin().initUser().method_calls,
            [('set', (GIDNUMBER, ['']), {}), 
            ('set', (HOMEDIRECTORY, '/home/%s' % USER), {})]
        )
        
        self.assertEqual(pyanaconda.users.libuser.admin().initGroup().method_calls,
            [('get', (GIDNUMBER,), {})])
        
    def check_user_exists_test(self):
        import pyanaconda.users     
 
        USER = 'TestUser'
 
        usr = pyanaconda.users.Users(self.anaconda)
        self.assertTrue(usr.checkUserExists(USER, root=''))
        self.assertEqual(pyanaconda.users.libuser.admin().method_calls, 
            [('lookupUserByName', (USER,), {})])        
    
    def get_pass_algo_md5_test(self):
        import pyanaconda.users      
        usr = pyanaconda.users.Users(self.anaconda)
        self.assertEqual(usr.getPassAlgo(), None)
        
    def set_user_password_test(self):
        import pyanaconda.users   
        
        USER = 'TestUser'
        PASS = 'abcde'
        CRYPTED = False
        LOCK = False
           
        usr = pyanaconda.users.Users(self.anaconda)
        usr.setUserPassword(USER, PASS, CRYPTED, LOCK)
        
        methods = [x[0] for x in pyanaconda.users.libuser.admin().method_calls]
        self.assertEqual(methods, 
            ['lookupUserByName', 'setpassUser', 'modifyUser'])
    
    def set_root_password_test(self):
        import pyanaconda.users   
                  
        usr = pyanaconda.users.Users(self.anaconda)
        usr.setRootPassword()        
        methods = [x[0] for x in pyanaconda.users.libuser.admin().method_calls]
        self.assertEqual(methods, 
            ['lookupUserByName', 'setpassUser', 'modifyUser'])      
    
    def writeks_test(self):
        import pyanaconda.users 
        usr = pyanaconda.users.Users(self.anaconda)
        
        f = self.fs.open('/test_file', 'w')
        usr.writeKS(f)
        f.close()
        
        import re
        self.assertTrue(
            re.match(r"rootpw[ ]+--iscrypted[ ]+.*\n", self.fs['/test_file']))
        
