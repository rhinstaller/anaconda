#!/usr/bin/python

import mock

class PackagingTest(mock.TestCase):
    
    def setUp(self):
        self.setupModules(["_isys", "logging"])
        
        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

        from pykickstart.version import makeVersion
        from pyanaconda.flags import flags

        # set some things specially since we're just testing
        flags.testing = True

        # set up ksdata
        self.ksdata = makeVersion()

        from pyanaconda.packaging import Payload
        self.payload = Payload(self.ksdata)

    def tearDown(self):
        self.tearDownModules()
        #os.system("rm -rf %s" % self.root)

    def payload_abstract_test(self):
        self.assertRaises(NotImplementedError, self.payload.setup, None)
        self.assertRaises(NotImplementedError, self.payload.description, None)

    def payload_repo_test(self):
        # ksdata repo list initially empty
        self.assertEqual(self.payload.data.repo.dataList(), [])

        # create and add a new ksdata repo
        repo_name = "test1"
        repo = self.ksdata.RepoData(name=repo_name, baseurl="http://localhost/")
        self.payload.addRepo(repo)

        # verify the repo was added
        self.assertEqual(self.payload.data.repo.dataList(), [repo])
        self.assertEqual(self.payload.getAddOnRepo(repo_name), repo)

        # remove the repo
        self.payload.removeRepo(repo_name)

        # verify the repo was removed
        self.assertEqual(self.payload.getAddOnRepo(repo_name), None)

    def payload_group_test(self):
        import pykickstart.constants
        from pykickstart.parser import Group

        # verify that ksdata group lists are initially empty
        self.assertEqual(self.payload.data.packages.groupList, [])
        self.assertEqual(self.payload.data.packages.excludedGroupList, [])

        self.payload.deselectGroup("core")
        self.assertEqual(self.payload.groupSelected("core"), False)

        # select a group and verify the selection is reflected afterward
        self.payload.selectGroup("core", optional=True)
        self.assertTrue(self.payload.groupSelected("core"))

        # verify the group is not in the excluded group list
        self.assertTrue(Group("core") not in self.payload.data.packages.excludedGroupList)

        # verify the include (optional/all) is recorded
        groups = self.payload.data.packages.groupList
        group = groups[[g.name for g in groups].index("core")]
        self.assertEqual(group.include, pykickstart.constants.GROUP_ALL)

        # select more groups
        self.payload.selectGroup("base")
        self.payload.selectGroup("development", default=False)

        # verify include types for newly selected groups
        group = groups[[g.name for g in groups].index("development")]
        self.assertEqual(group.include, pykickstart.constants.GROUP_REQUIRED)

        group = groups[[g.name for g in groups].index("base")]
        self.assertEqual(group.include, pykickstart.constants.GROUP_DEFAULT)

        # deselect a group and verify the set of groups is correct afterward
        self.payload.deselectGroup("base")
        self.assertFalse(self.payload.groupSelected("base"))
        self.assertTrue(self.payload.groupSelected("core"))
        self.assertTrue(self.payload.groupSelected("development"))

    def payload_package_test(self):
        # verify that ksdata package lists are initially empty
        self.assertEqual(self.payload.data.packages.packageList, [])
        self.assertEqual(self.payload.data.packages.excludedList, [])

        name = "vim-common"

        # deselect a package
        self.payload.deselectPackage(name)
        self.assertEqual(self.payload.packageSelected(name), False)

        # select the same package and verify it
        self.payload.selectPackage(name)
        self.assertEqual(self.payload.packageSelected(name), True)
        self.assertTrue(name in self.payload.data.packages.packageList)
        self.assertFalse(name in self.payload.data.packages.excludedList)

        # select some other packages
        self.payload.selectPackage("bash")
        self.payload.selectPackage("gnote")

        # deselect one of them and then verify the selection state of them all
        self.payload.deselectPackage("bash")
        self.assertFalse(self.payload.packageSelected("bash"))
        self.assertTrue(self.payload.packageSelected("gnote"))
        self.assertTrue(self.payload.packageSelected(name))

    def payload_get_release_version_test(self):
        # Given no URL, _getReleaseVersion should be able to get a releasever
        # from pyanaconda.constants.productVersion. This trickery is due to the
        # fact that pyanaconda/packaging/__init__.py will have already imported
        # productVersion from pyanaconda.constants.
        import pyanaconda.packaging
        pyanaconda.packaging.productVersion = "17-Beta"
        self.assertEqual(self.payload._getReleaseVersion(None), "17")
