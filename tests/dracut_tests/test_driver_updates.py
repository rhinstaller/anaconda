# test_driver_updates.py - unittests for driver_updates.py

import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock

import os
import tempfile
import shutil
import collections

import sys
sys.path.append(os.path.normpath(os.path.dirname(__file__)+'/../../dracut'))

from driver_updates import copy_files, move_files, iter_files, ensure_dir
from driver_updates import append_line, mkdir_seq


def touch(path):
    try:
        open(path, 'a')
    except IOError as e:
        if e.errno != 17: raise


def makedir(path):
    ensure_dir(path)
    return path


def makefile(path):
    makedir(os.path.dirname(path))
    touch(path)
    return path


def makefiles(*paths):
    return [makefile(p) for p in paths]


def listfiles(path):
    path = os.path.normpath(path)

    # This could be a list comprehension, or it could be readable
    for dirpath, _dirname, filenames in os.walk(path):
        for filename in filenames:
            # Strip "path" from dirname so that the paths are relative to path.
            # If dirname != path, add one to the length to keep the slash
            # in path/subdir.
            if dirpath == path:
                prefix = ''
            else:
                prefix = dirpath[len(path)+1:] + '/'
            yield prefix + filename


class FileTestCaseBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_driver_updates.")
        self.srcdir = self.tmpdir+'/src/'
        self.destdir = self.tmpdir+'/dest/'

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def makefiles(self, *paths):
        return [makefile(os.path.normpath(self.tmpdir+'/'+p)) for p in paths]


class SelfTestCase(FileTestCaseBase):
    def test_makefiles(self):
        """check test helpers"""
        filepaths = ["sub/dir/test.file", "testfile"]
        self.makefiles(*filepaths)
        for f in filepaths:
            self.assertTrue(os.path.exists(self.tmpdir+'/'+f))


class TestCopyFiles(FileTestCaseBase):
    def test_basic(self):
        """copy_file: copy files into destdir, leaving existing contents"""
        files = self.makefiles("src/file1", "src/subdir/file2")
        self.makefiles("dest/file3")
        copy_files(files, self.destdir, self.srcdir)
        result = set(listfiles(self.destdir))
        self.assertEqual(result, set(["file1", "subdir/file2", "file3"]))

    def test_overwrite(self):
        """copy_file: overwrite files in destdir if they have the same name"""
        src, dest = self.makefiles("src/file1", "dest/file1")
        with open(src, 'w') as outf:
            outf.write("srcfile")
        with open(dest, 'w') as outf:
            outf.write("destfile")
        copy_files([src], self.destdir, self.srcdir)
        self.assertEqual(list(listfiles(self.destdir)), ["file1"])
        self.assertEqual(open(dest).read(), "srcfile")

    def test_samefile(self):
        """copy_file: skip files already in destdir"""
        (dest,) = self.makefiles("dest/file1")
        with open(dest, 'w') as outf:
            outf.write("destfile")
        copy_files([dest], self.destdir, "src")
        self.assertEqual(list(listfiles(self.destdir)), ["file1"])
        self.assertEqual(open(dest).read(), "destfile")

    def test_copy_to_parent(self):
        """copy_file: skip files in subdirs of destdir"""
        files = self.makefiles("dest/subdir/file1")
        copy_files(files, self.destdir, "src")
        self.assertEqual(list(iter_files(self.destdir)), files)

    def test_copy_kernel(self):
        """copy_file: strip leading module directories"""
        files = self.makefiles("src/lib/modules/3.2.1-900.fc47.x86_64/kernel/subdir/module.ko",
                               "src/lib/modules/3.2.1-900.fc47.x86_64/kernel/other.ko.xz")
        copy_files(files, self.destdir, self.srcdir+"/lib/modules")
        result = set(listfiles(self.destdir))
        self.assertEqual(result, set(["subdir/module.ko", "other.ko.xz"]))


class TestIterFiles(FileTestCaseBase):
    def test_basic(self):
        """iter_files: iterates over full paths to files under topdir"""
        files = set(self.makefiles("src/file1", "dest/file2", "src/sub/file3"))
        makedir(self.tmpdir+'/empty/dir')
        result = set(iter_files(self.tmpdir))
        self.assertEqual(files, result)

    def test_pattern(self):
        """iter_files: match filename against glob pattern"""
        self.makefiles("src/file1.so", "src/sub.ko/file2")
        goodfiles = set(self.makefiles("src/sub/file1.ko", "src/file2.ko.xz"))
        result = set(iter_files(self.tmpdir, pattern="*.ko*"))
        self.assertEqual(result, goodfiles)


class TestMoveFiles(FileTestCaseBase):
    def test_basic(self):
        """move_files: move files to destdir"""
        files = self.makefiles("src/file1", "src/subdir/file2")
        move_files(files, self.destdir, self.srcdir)
        self.assertEqual(set(listfiles(self.destdir)), set(["file1", "subdir/file2"]))
        self.assertEqual(list(iter_files(self.srcdir)), [])

    def test_overwrite(self):
        """move_files: overwrite files with the same name"""
        src, dest = self.makefiles("src/file1", "dest/file1")
        with open(src, 'w') as outf:
            outf.write("srcfile")
        with open(dest, 'w') as outf:
            outf.write("destfile")
        move_files([src], self.destdir, self.srcdir)
        self.assertEqual(list(listfiles(self.destdir)), ["file1"])
        self.assertEqual(open(dest).read(), "srcfile")
        self.assertEqual(list(iter_files(self.srcdir)), [])

    def test_samefile(self):
        """move_files: leave files alone if they're already in destdir"""
        (dest,) = self.makefiles("dest/file1")
        with open(dest, 'w') as outf:
            outf.write("destfile")
        move_files([dest], self.destdir, self.srcdir)
        self.assertEqual(list(listfiles(self.destdir)), ["file1"])
        self.assertEqual(open(dest).read(), "destfile")

    def test_move_to_parent(self):
        """move_files: leave files alone if they're in a subdir of destdir"""
        files = set(self.makefiles("dest/subdir/file1", "dest/file2"))
        move_files(files, self.destdir, self.srcdir)
        self.assertEqual(set(iter_files(self.destdir)), files)


class TestAppendLine(FileTestCaseBase):
    def test_empty(self):
        """append_line: create file + append \\n when needed"""
        line = "this is a line of text with no newline"
        outfile = self.tmpdir+'/outfile'
        append_line(outfile, line)
        self.assertEqual(open(outfile).read(), line+'\n')

    def test_append(self):
        """append_line: adds a line to the end of an existing file"""
        oldlines = ["line one", "line two", "and I'm line three"]
        outfile = self.tmpdir+'/outfile'
        with open(outfile, 'w') as outf:
            for line in oldlines:
                outf.write(line+'\n')
        line = "this line contains a newline already\n"
        append_line(outfile, line)
        self.assertEqual(open(outfile).read(), '\n'.join(oldlines+[line]))


from driver_updates import read_lines
class TestReadLine(FileTestCaseBase):
    def test_empty(self):
        """read_lines: return [] for empty file"""
        [empty] = self.makefiles("emptyfile")
        self.assertEqual(read_lines(empty), [])

    def test_missing(self):
        """read_lines: return [] for missing file"""
        self.assertEqual(read_lines(self.tmpdir+'/no-such-file'),[])

    def test_readlines(self):
        """read_lines: returns a list of lines without trailing newlines"""
        filedata = 'line one\nline two\n\nline four\n'
        outfile = self.tmpdir+'/outfile'
        with open(outfile, 'w') as outf:
            outf.write(filedata)
        lines = read_lines(outfile)
        self.assertEqual(lines, ['line one', 'line two','','line four'])

    def test_readline_and_append_line(self):
        """read_lines: returns items as passed to append_line"""
        filename = self.tmpdir+'/outfile'
        items = ["one", "two", "five"]
        for i in items:
            append_line(filename, i)
        self.assertEqual(items, read_lines(filename))


class TestMkdirSeq(FileTestCaseBase):
    def test_basic(self):
        """mkdir_seq: first dir ends with 1"""
        newdir = mkdir_seq(self.srcdir+'/DD-')
        self.assertEqual(newdir, self.srcdir+'/DD-1')
        self.assertTrue(os.path.isdir(newdir))

    def test_one_exists(self):
        """mkdir_seq: increment number if file exists"""
        firstdir = mkdir_seq(self.srcdir+'/DD-')
        newdir = mkdir_seq(self.srcdir+'/DD-')
        self.assertEqual(newdir, self.srcdir+'/DD-2')
        self.assertTrue(os.path.isdir(newdir))
        self.assertTrue(os.path.isdir(firstdir))


from driver_updates import find_repos, save_repo, ARCH
# As far as we know, this is what makes a valid repo: rhdd3 + rpms/`uname -m`/
def makerepo(topdir, desc=None):
    descfile = makefile(topdir+'/rhdd3')
    if not desc:
        desc = os.path.basename(topdir)
    with open(descfile, "w") as outf:
        outf.write(desc+"\n")
    makedir(topdir+'/rpms/'+ARCH)


def makerepodata(topdir):
    makedir(topdir + '/repodata/')
    makefile(topdir + '/repodata/repomd.xml')
    makefile(topdir + '/repodata/filelists.xml.gz')
    makefile(topdir + '/repodata/primary.xml.gz')
    makefile(topdir + '/repodata/other.xml.gz')


class TestFindRepos(FileTestCaseBase):
    def test_basic(self):
        """find_repos: return RPM dir if a valid repo is found"""
        makerepo(self.tmpdir)
        repos = find_repos(self.tmpdir)
        self.assertEqual(repos, [self.tmpdir+'/rpms/'+ARCH])
        self.assertTrue(os.path.isdir(repos[0]))

    def test_multiple_subdirs(self):
        """find_repos: descend multiple subdirs if needed"""
        makerepo(self.tmpdir+'/driver1')
        makerepo(self.tmpdir+'/sub/driver1')
        makerepo(self.tmpdir+'/sub/driver2')
        repos = find_repos(self.tmpdir)
        self.assertEqual(len(repos),3)


class TestSaveRepo(FileTestCaseBase):
    def test_folder_repo(self):
        """save_repo: copies directory contents to /run/install/DD-X"""
        makerepo(self.srcdir)
        repo = find_repos(self.srcdir)[0]
        makerepodata(repo)
        makefile(repo + '/fake-something1.rpm')
        makefile(repo + '/fake-something2.rpm')
        makefile(repo + '/fake-something3.rpm')
        saved = save_repo(repo, target=self.destdir)
        expected_files = set(["fake-something1.rpm", "fake-something2.rpm",
                              "fake-something3.rpm", "repodata/repomd.xml",
                              "repodata/filelists.xml.gz",
                              "repodata/primary.xml.gz",
                              "repodata/other.xml.gz"])
        self.assertEqual(set(listfiles(saved)), expected_files)
        self.assertEqual(saved, os.path.join(self.destdir, "DD-1"))

    def test_single_file(self):
        """save_repo: copies a single file to /run/install/DD-X"""
        makerepo(self.srcdir)
        repo = find_repos(self.srcdir)[0]
        file_path = makefile(repo + '/fake-something1.rpm')
        makefile(repo + '/fake-something2.rpm')
        makefile(repo + '/fake-something3.rpm')
        saved = save_repo(file_path, target=self.destdir)
        # check that only the single file was copied
        self.assertEqual(set(listfiles(saved)), set(["fake-something1.rpm"]))
        self.assertEqual(saved, os.path.join(self.destdir, "DD-1"))

    def test_multiple_repo_folders(self):
        """save_repo: copies directory contents to multiple /run/install/DD-X folders"""
        # create multiple repos
        repo_folder_1 = os.path.join(self.srcdir, "repo1")
        repo_folder_2 = os.path.join(self.srcdir, "repo2")
        repo_folder_3 = os.path.join(self.srcdir, "repo3")
        makerepo(repo_folder_1)
        makerepo(repo_folder_2)
        makerepo(repo_folder_3)
        repo1 = find_repos(repo_folder_1)[0]
        repo2 = find_repos(repo_folder_2)[0]
        repo3 = find_repos(repo_folder_3)[0]

        # fill them with fake driver disk RPMs
        for repo in [repo1, repo2, repo3]:
            makefile(repo + '/repodata')
            makefile(repo + '/fake-something1.rpm')
            makefile(repo + '/fake-something2.rpm')
            makefile(repo + '/fake-something3.rpm')

        # copy their contents
        # -> content of each repo should apprently end in a separate /run/install/DD-X folder
        # -> we will attempt to copy the full content of the first two repos in full
        #    and just a single RPM from the third repo
        saved1 = save_repo(repo1, target=self.destdir)
        saved2 = save_repo(repo2, target=self.destdir)
        file_path = repo3 + "/fake-something2.rpm"
        saved3 = save_repo(file_path, target=self.destdir)

        # check that everything was copied correctly
        full_copy_expected_files = set(["fake-something1.rpm", "fake-something2.rpm", "fake-something3.rpm", "repodata"])
        self.assertEqual(set(listfiles(saved1)), full_copy_expected_files)
        self.assertEqual(saved1, os.path.join(self.destdir, "DD-1"))
        self.assertEqual(set(listfiles(saved2)), full_copy_expected_files)
        self.assertEqual(saved2, os.path.join(self.destdir, "DD-2"))
        self.assertEqual(set(listfiles(saved3)), set(["fake-something2.rpm"]))
        self.assertEqual(saved3, os.path.join(self.destdir, "DD-3"))

from driver_updates import mount, umount, mounted
class MountTestCase(unittest.TestCase):
    @mock.patch('driver_updates.mkdir_seq')
    @mock.patch('driver_updates.subprocess.check_call')
    def test_mkdir(self, check_call, mkdir):
        """mount: makes mountpoint if needed"""
        dev, mnt = '/dev/fake', '/media/DD-1'
        mkdir.return_value = mnt
        mountpoint = mount(dev)
        mkdir.assert_called_once_with('/media/DD-')
        check_call.assert_called_once_with(["mount", dev, mnt])
        self.assertEqual(mnt, mountpoint)

    @mock.patch('driver_updates.mkdir_seq')
    @mock.patch('driver_updates.subprocess.check_call')
    def test_basic(self, check_call, mkdir):
        """mount: calls mount(8) to mount a device/image"""
        dev, mnt = '/dev/fake', '/media/fake'
        mount(dev, mnt)
        check_call.assert_called_once_with(["mount", dev, mnt])
        self.assertFalse(mkdir.called)

    @mock.patch('driver_updates.subprocess.call')
    def test_umount(self, call):
        """umount: calls umount(8)"""
        mnt = '/mnt/fake'
        umount(mnt)
        call.assert_called_once_with(["umount", mnt])

    @mock.patch('driver_updates.mount')
    @mock.patch('driver_updates.umount')
    def test_mount_manager(self, mock_umount, mock_mount):
        """mounted: context manager mounts/umounts as expected"""
        dev, mnt = '/dev/fake', '/media/fake'
        mock_mount.return_value = mnt
        with mounted(dev, mnt) as mountpoint:
            mock_mount.assert_called_once_with(dev, mnt)
            self.assertFalse(mock_umount.called)
            self.assertEqual(mountpoint, mnt)
        mock_umount.assert_called_once_with(mnt)


# NOTE: dd_list and dd_extract get tested pretty thoroughly in tests/dd_tests,
# so this is a slightly higher-level test case
from driver_updates import dd_list, dd_extract, Driver
fake_module = Driver(
    source='/repo/path/to/fake-driver-1.0-1.rpm',
    name='fake-driver',
    flags='modules firmwares',
    description='Wow this is totally a fake driver.\nHooray for this',
    repo='/repo/path/to'
)
fake_enhancement = Driver(
    source='/repo/path/to/fake-enhancement-1.0-1.rpm',
    name='fake-enhancement',
    flags='binaries libraries',
    description='This is enhancing the crap out of the installer.\n\nYeah.',
    repo=fake_module.repo
)


def dd_list_output(driver):
    out='{0.source}\n{0.name}\n{0.flags}\n{0.description}\n---\n'.format(driver)
    return out.encode('utf-8')


class DDUtilsTestCase(unittest.TestCase):
    @mock.patch("driver_updates.subprocess.check_output")
    def test_dd_list(self, check_output):
        """dd_list: returns a list of Driver objects parsed from output"""
        output = dd_list_output(fake_module)+dd_list_output(fake_enhancement)
        check_output.return_value = output
        anaconda, kernel = '19.0', os.uname()[2]
        result = dd_list(fake_module.repo)
        cmd = check_output.call_args[0][0]
        self.assertIn(kernel, cmd)
        self.assertIn(anaconda, cmd)
        self.assertIn(fake_module.repo, cmd)
        self.assertTrue(cmd[0].endswith("dd_list"))
        self.assertEqual(len(result), 2)
        mod, enh = sorted(result, key=lambda d: d.name)
        self.assertEqual(mod.__dict__, fake_module.__dict__)
        self.assertEqual(enh.__dict__, fake_enhancement.__dict__)

    @mock.patch("driver_updates.subprocess.check_output")
    def test_dd_extract(self, check_output):
        """dd_extract: call binary with expected arguments"""
        rpm = "/some/kind/of/path.rpm"
        outdir = "/output/dir"
        dd_extract(rpm, outdir)
        cmd = check_output.call_args[0][0]
        self.assertIn(os.uname()[2], cmd)
        self.assertIn(rpm, cmd)
        self.assertIn(outdir, cmd)
        self.assertIn("-blmf", cmd)
        self.assertTrue(cmd[0].endswith("dd_extract"))


from driver_updates import extract_drivers, grab_driver_files, load_drivers

@mock.patch("driver_updates.ensure_dir")
@mock.patch("driver_updates.save_repo")
@mock.patch("driver_updates.append_line")
@mock.patch("driver_updates.dd_extract")
class ExtractDriversTestCase(unittest.TestCase):
    def test_drivers(self, mock_extract, mock_append, mock_save, *args):
        """extract_drivers: save repo, write pkglist"""
        extract_drivers(drivers=[fake_enhancement, fake_module])
        # extracts all listed modules
        mock_extract.assert_has_calls([
            mock.call(fake_enhancement.source, "/updates"),
            mock.call(fake_module.source, "/updates")
        ], any_order=True)
        pkglist = "/run/install/dd_packages"
        mock_append.assert_called_once_with(pkglist, fake_module.name)
        mock_save.assert_called_once_with(fake_module.repo)

    def test_enhancements(self, mock_extract, mock_append, mock_save, *args):
        """extract_drivers: extract selected drivers, don't save enhancements"""
        extract_drivers(drivers=[fake_enhancement])
        mock_extract.assert_called_once_with(
            fake_enhancement.source, "/updates"
        )
        self.assertFalse(mock_append.called)
        self.assertFalse(mock_save.called)

    def test_repo(self, mock_extract, mock_append, mock_save, *args):
        """extract_drivers(repos=[...]) extracts all drivers from named repos"""
        with mock.patch("driver_updates.dd_list", side_effect=[
            [fake_enhancement],
            [fake_enhancement, fake_module]]):
            extract_drivers(repos=['enh_repo', 'mod_repo'])
        mock_extract.assert_has_calls([
            mock.call(fake_enhancement.source, "/updates"),
            mock.call(fake_enhancement.source, "/updates"),
            mock.call(fake_module.source, "/updates")
        ])
        pkglist = "/run/install/dd_packages"
        mock_append.assert_called_once_with(pkglist, fake_module.name)
        mock_save.assert_called_once_with(fake_module.repo)


class GrabDriverFilesTestCase(FileTestCaseBase):
    def test_basic(self):
        """grab_driver_files: copy drivers into place, return module+alias dict"""
        # create a bunch of fake extracted files
        outdir = self.tmpdir + '/extract-outdir'
        moddir = outdir + "/lib/modules/%s/kernel/" % os.uname()[2]
        fwdir = outdir + "/lib/firmware/"
        modules = makefiles(moddir+"net/funk.ko", moddir+"fs/lolfs.ko.xz")
        firmware = makefiles(fwdir+"funk.fw", fwdir+"fs/lolfs.fw")
        makefiles(outdir+"/usr/bin/monkey", outdir+"/other/dir/blah.ko")
        mod_upd_dir = self.tmpdir+'/module-updates'
        fw_upd_dir = self.tmpdir+'/fw-updates'
        # use our updates dirs instead of the default updates dirs
        with mock.patch.multiple("driver_updates",
                                 MODULE_UPDATES_DIR=mod_upd_dir,
                                 FIRMWARE_UPDATES_DIR=fw_upd_dir,
                                 list_aliases=lambda _x: []):
            moddict = grab_driver_files(outdir)

        self.assertEqual(moddict, {"funk": [], "lolfs": []})
        modfiles = set(['net/funk.ko', 'fs/lolfs.ko.xz'])
        fwfiles = set(['funk.fw', 'fs/lolfs.fw'])
        # modules/firmware are *not* in their old locations
        self.assertEqual([f for f in modules+firmware if os.path.exists(f)], [])
        # modules are in the system's updates dir
        self.assertEqual(set(listfiles(mod_upd_dir)), modfiles)
        # modules are also in outdir's updates dir
        self.assertEqual(set(listfiles(outdir+'/'+mod_upd_dir)), modfiles)
        # repeat for firmware
        self.assertEqual(set(listfiles(fw_upd_dir)), fwfiles)
        self.assertEqual(set(listfiles(outdir+'/'+fw_upd_dir)), fwfiles)


class LoadDriversTestCase(unittest.TestCase):
    @mock.patch("driver_updates.subprocess.call")
    @mock.patch("driver_updates.rm_net_intfs_for_unload")
    @mock.patch("driver_updates.list_net_intfs")
    def test_basic(self, list_net_intfs, rm_net_intfs_for_unload, call):
        """load_drivers: runs depmod and modprobes all named modules"""
        modnames = ['mod1', 'mod2']
        moddict = collections.OrderedDict({name: [name] for name in modnames})
        load_drivers(collections.OrderedDict(moddict))
        call.assert_has_calls([
            mock.call(["depmod", "-a"]),
            mock.call(["modprobe", "-a"] + list(moddict.keys()))
        ])

    @mock.patch("driver_updates.subprocess.call")
    @mock.patch("driver_updates.subprocess.check_output", return_value="sorbet")
    @mock.patch("driver_updates.rm_net_intfs_for_unload", return_value=set())
    @mock.patch("driver_updates.list_net_intfs", return_value=set())
    def test_basic_replace(self, list_net_intfs, rm_net_intfs_for_unload, check_output, call):
        # "icecream" is the updated driver, replacing "sorbet"
        # the check_output patch intercepts 'modprobe -R <alias>'
        load_drivers({"icecream": ['pineapple', 'cherry', 'icecream']})
        call.assert_has_calls([
            mock.call(["modprobe", "-r", "sorbet"]),
            mock.call(["depmod", "-a"]),
            mock.call(["modprobe", "-a", "icecream"])
        ])

    @mock.patch("driver_updates.subprocess.call")
    @mock.patch("driver_updates.subprocess.check_output", return_value="sorbet")
    @mock.patch("driver_updates.rm_net_intfs_for_unload", return_value=set())
    @mock.patch("driver_updates.list_net_intfs", return_value=set())
    @mock.patch("driver_updates.get_all_loaded_modules")
    def test_reload_module_dependencies(self, get_all_loaded_modules, list_net_intfs, rm_net_intfs_for_unload, check_output, call):
        # "icecream" has module dependency "cornet" which will be unloaded because of
        # dependencies and must be reload back
        mod_dependencies=[["icecream", "cornet"], ["icecream"]]
        get_all_loaded_modules.side_effect = lambda: mod_dependencies.pop(0)

        load_drivers({"icecream": ['pineapple', 'cherry', 'icecream']})
        call.assert_has_calls([
            mock.call(["modprobe", "-r", "sorbet"]),
            mock.call(["depmod", "-a"]),
            mock.call(["modprobe", "-a", "icecream"]),
            mock.call(["modprobe", "-a", "cornet"])
        ])

    @mock.patch("driver_updates.subprocess.call")
    @mock.patch("driver_updates.subprocess.check_call")
    @mock.patch("driver_updates.subprocess.check_output")
    @mock.patch("driver_updates.list_net_intfs")
    def test_interface_unload(self, list_net_intfs, check_output, check_call, call):
        # mode is net mode, remove dracut configuration for interface,
        # retrigger udev event
        intfs = ["ens3", "", "ens3"]
        list_net_intfs.side_effect = lambda: set(intfs.pop())

        def patched_check_output(command, stderr=None):
            if command[0] == "modprobe":
                return "mod1"
            elif command[0] == "find-net-intfs-by-driver":
                return "ens3"
        check_output.side_effect = patched_check_output

        load_drivers({"mod1": ["mod1"]})
        call.assert_has_calls([
            mock.call(["modprobe", "-r", "mod1"]),
            mock.call(["depmod", "-a"]),
            mock.call(["modprobe", "-a", "mod1"]),
        ])
        check_call.assert_has_calls([
            mock.call(["anaconda-ifdown", "ens3"])
        ])


from driver_updates import process_driver_disk
class ProcessDriverDiskTestCase(unittest.TestCase):
    def setUp(self):
        # an iterable that returns fake mountpoints, for mocking mount()
        self.fakemount = ["/mnt/DD-%i" % n for n in range(1,10)]
        # an iterable that returns fake repos, for mocking find_repos()
        self.frepo = {
            '/mnt/DD-1': ['/mnt/DD-1/repo1'],
            '/mnt/DD-2': ['/mnt/DD-2/repo1', '/mnt/DD-2/repo2'],
        }
        # fake iso listings for iso_dir
        self.fiso = {
            '/mnt/DD-1': [],
            '/mnt/DD-2': [],
            '/mnt/DD-3': [],
        }
        # a context-manager object to be returned by the mock mounted()
        mounted_ctx = mock.MagicMock(
            __enter__=mock.MagicMock(side_effect=self.fakemount), # mount
            __exit__=mock.MagicMock(return_value=None),           # umount
        )
        self.moddict = {}
        # set up our patches
        patches = (
            mock.patch("driver_updates.mounted", return_value=mounted_ctx),
            mock.patch("driver_updates.find_repos", side_effect=self.frepo.get),
            mock.patch("driver_updates.find_isos", side_effect=self.fiso.get),
            mock.patch("driver_updates.extract_drivers", return_value=True),
            mock.patch('driver_updates.grab_driver_files',
                                side_effect=lambda: self.moddict),
        )
        self.mocks = {p.attribute:p.start() for p in patches}
        for p in patches: self.addCleanup(p.stop)

    def test_basic(self):
        """process_driver_disk: mount disk, extract RPMs, grab + load drivers"""
        dev = '/dev/fake'
        process_driver_disk(dev)
        # did we mount the initial device, and then the .iso we find therein?
        self.mocks['mounted'].assert_called_once_with(dev)
        self.mocks['extract_drivers'].assert_called_once_with(repos=self.frepo['/mnt/DD-1'])
        self.mocks['grab_driver_files'].assert_called_once_with()

    def test_recursive(self):
        """process_driver_disk: recursively process .isos at toplevel"""
        dev = '/dev/fake'
        # first mount has no repos, but an iso
        self.frepo['/mnt/DD-1'] = []
        self.fiso['/mnt/DD-1'].append('magic.iso')
        self.fiso['/mnt/DD-2'].append('ignored.iso')
        process_driver_disk(dev)
        # did we mount the initial device, and the iso therein?
        # also: we ignore ignored.iso because magic.iso is a proper DD
        self.mocks['mounted'].assert_has_calls([
            mock.call(dev), mock.call('magic.iso')
        ])
        # we extracted drivers from the repo(s) in magic.iso
        self.mocks['extract_drivers'].assert_called_once_with(repos=self.frepo['/mnt/DD-2'])
        self.mocks['grab_driver_files'].assert_called_once_with()

    def test_no_drivers(self):
        """process_driver_disk: don't run depmod etc. if no new drivers"""
        dev = '/dev/fake'
        self.mocks['extract_drivers'].return_value = False
        process_driver_disk(dev)
        self.assertFalse(self.mocks['grab_driver_files'].called)


from driver_updates import process_driver_rpm
class ProcessDriverRPMTestCase(unittest.TestCase):
    def setUp(self):
        self.frepo = {
            '/tmp/fake': ['/mnt/DD-1'],
        }
        self.moddict = {}
        # set up our patches
        patches = (
            mock.patch("driver_updates.find_repos", side_effect=self.frepo.get),
            mock.patch("driver_updates.extract_drivers", return_value=True),
            mock.patch('driver_updates.grab_driver_files',
                                side_effect=lambda: self.moddict),
        )
        self.mocks = {p.attribute:p.start() for p in patches}
        for p in patches: self.addCleanup(p.stop)

    def test_basic(self):
        """process_driver_rpm: extract RPM, grab + load driver"""
        rpm = '/tmp/fake/driver.rpm'
        process_driver_rpm(rpm)
        self.mocks['extract_drivers'].assert_called_once_with(repos=["/tmp/fake/driver.rpm"])
        self.mocks['grab_driver_files'].assert_called_once_with()


from driver_updates import finish, mark_finished, all_finished

class FinishedTestCase(FileTestCaseBase):
    def test_mark_finished(self):
        """mark_finished: appends a line to /tmp/dd_finished"""
        requeststr = "WOW SOMETHING OR OTHER"
        mark_finished(requeststr, topdir=self.tmpdir)
        finished = self.tmpdir+'/dd_finished'
        self.assertTrue(os.path.exists(finished))
        self.assertEqual(read_lines(finished), [requeststr])

    def test_all_finished(self):
        """all_finished: True if all lines from dd_todo are in dd_finished"""
        todo = self.tmpdir+'/dd_todo'
        requests = ['one', 'two', 'final thingy']
        with open(todo, 'w') as outf:
            outf.write(''.join(r+'\n' for r in requests))
        self.assertEqual(set(read_lines(todo)), set(requests))
        for r in reversed(requests):
            self.assertFalse(all_finished(topdir=self.tmpdir))
            mark_finished(r, topdir=self.tmpdir)
        self.assertTrue(all_finished(topdir=self.tmpdir))

    def test_extra_finished(self):
        """all_finished: True if dd_finished has more items than dd_todo"""
        self.test_all_finished()
        mark_finished("BONUS", topdir=self.tmpdir)
        self.assertTrue(all_finished(topdir=self.tmpdir))

    def test_finish(self):
        """finish: mark request finished, and write dd.done if all complete"""
        todo = self.tmpdir+'/dd_todo'
        done = self.tmpdir+'/dd.done'
        requests = ['one', 'two', 'final thingy']
        with open(todo, 'w') as outf:
            outf.write(''.join(r+'\n' for r in requests))
        for r in reversed(requests):
            print("marking %s" % r)
            self.assertFalse(os.path.exists(done))
            finish(r, topdir=self.tmpdir)
        self.assertTrue(os.path.exists(done))


from driver_updates import get_deviceinfo, DeviceInfo
blkid_out = b'''\
DEVNAME=/dev/sda2
UUID=0f21a3d1-dcd3-4ab4-a292-c5556850d561
TYPE=ext4

DEVNAME=/dev/sda1
UUID=C53C-EE46
TYPE=vfat

DEVNAME=/dev/sda3
UUID=4126dbb6-c7d3-47b4-b1fc-9bb461df0067
TYPE=btrfs

DEVNAME=/dev/loop0
UUID=6f16967e-0388-4276-bd8d-b88e5b217a55
TYPE=ext4
'''
disk_labels = {
    '/dev/sdb1': 'metroid_srv',
    '/dev/loop0': 'I\\x20\u262d\\x20COMMUNISM',
    '/dev/sda3': 'metroid_root'
}
devicelist = [
    DeviceInfo(DEVNAME='/dev/sda2', TYPE='ext4',
               UUID='0f21a3d1-dcd3-4ab4-a292-c5556850d561'),
    DeviceInfo(DEVNAME='/dev/sda1', TYPE='vfat',
               UUID='C53C-EE46'),
    DeviceInfo(DEVNAME='/dev/sda3', TYPE='btrfs', LABEL='metroid_root',
               UUID='4126dbb6-c7d3-47b4-b1fc-9bb461df0067'),
    DeviceInfo(DEVNAME='/dev/loop0', TYPE='ext4',
               LABEL='I\\x20\u262d\\x20COMMUNISM',
               UUID='6f16967e-0388-4276-bd8d-b88e5b217a55'),
]


# also covers blkid, get_disk_labels, DeviceInfo
class DeviceInfoTestCase(unittest.TestCase):
    @mock.patch('driver_updates.subprocess.check_output',return_value=blkid_out)
    @mock.patch('driver_updates.get_disk_labels',return_value=disk_labels)
    def test_basic(self, get_disk_labels, check_output):
        """get_deviceinfo: parses DeviceInfo from blkid etc."""
        disks = get_deviceinfo()
        self.assertEqual(len(disks), 4)
        disks.sort(key=lambda d: d.device)
        loop, efi, boot, root = disks
        self.assertEqual(vars(boot), vars(devicelist[0]))
        self.assertEqual(vars(efi), vars(devicelist[1]))
        self.assertEqual(vars(root), vars(devicelist[2]))
        self.assertEqual(vars(loop), vars(devicelist[3]))

    def test_shortdev(self):
        d = DeviceInfo(DEVNAME="/dev/disk/by-label/OEMDRV")
        with mock.patch("os.path.realpath", return_value="/dev/i2o/hdb"):
            self.assertEqual(d.shortdev, "i2o/hdb")

# TODO: test TextMenu itself

# py2/3 compat
if sys.version_info.major == 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO


from driver_updates import device_menu
class DeviceMenuTestCase(unittest.TestCase):
    def setUp(self):
        patches = (
            mock.patch('driver_updates.get_deviceinfo',return_value=devicelist),
        )
        self.mocks = {p.attribute:p.start() for p in patches}
        for p in patches: self.addCleanup(p.stop)

    def test_device_menu_exit(self):
        """device_menu: 'c' exits the menu"""
        with mock.patch('driver_updates._input', side_effect=['c']):
            dev = device_menu()
        self.assertEqual(dev, [])
        self.assertEqual(self.mocks['get_deviceinfo'].call_count, 1)

    def test_device_menu_refresh(self):
        """device_menu: 'r' makes the menu refresh"""
        with mock.patch('driver_updates._input', side_effect=['r','c']):
            device_menu()
        self.assertEqual(self.mocks['get_deviceinfo'].call_count, 2)

    @mock.patch("sys.stdout", new_callable=StringIO)
    def test_device_menu(self, stdout):
        """device_menu: choosing a number returns that Device"""
        choose_num='2'
        with mock.patch('driver_updates._input', return_value=choose_num):
            result = device_menu()
        # if you hit '2' you should get the corresponding device from the list
        self.assertEqual(len(result), 1)
        dev = result[0]
        self.assertEqual(vars(dev), vars(devicelist[int(choose_num)-1]))
        # find the corresponding line on-screen
        screen = [l.strip() for l in stdout.getvalue().splitlines()]
        match = [l for l in screen if l.startswith(choose_num+')')]
        self.assertEqual(len(match), 1)
        line = match.pop(0)
        # the device name (at least) should be on this line
        self.assertIn(os.path.basename(dev.device), line)


from driver_updates import list_aliases
class ListAliasesTestCase(unittest.TestCase):
    @mock.patch('driver_updates.subprocess.check_output', return_value="alias1\nalias2\n")
    def test_basic(self, check_output):
        modname = "fake_module"
        alias_list = list_aliases(modname)

        check_output.assert_called_once_with(["modinfo", "-F", "alias", modname])
        self.assertEqual(alias_list, ["alias1", "alias2", modname])
