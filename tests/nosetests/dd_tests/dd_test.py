# unit tests for driver disk utilities (utils/dd)

import os
import shutil
import unittest
import tempfile
import subprocess

from abc import ABC

from contextlib import contextmanager
from collections import namedtuple
from rpmfluff import SourceFile, GeneratedSourceFile, SimpleRpmBuild, expectedArch, make_elf
from shutup import shutup

TOP_SRCDIR = os.environ.get("top_builddir", "../..")
UTILDIR = os.path.join(TOP_SRCDIR, "utils/dd")

# helpers for calling the utilities
Driver = namedtuple("Driver", "source name flags description")


def dd_list(dd_path, kernel_ver, anaconda_ver):
    out = subprocess.check_output([os.path.join(UTILDIR, "dd_list"),
                                   '-d', dd_path,
                                   '-k', kernel_ver,
                                   '-a', anaconda_ver],
                                  stderr=open('/dev/null')).decode('utf-8')
    return [Driver(*d.split('\n', 3)) for d in out.split('\n---\n')[:-1]]


def dd_extract(rpm_path, outdir, kernel_ver, flags='-blmf'):
    out = subprocess.check_output([os.path.join(UTILDIR, "dd_extract"),
                                   flags,
                                   '-r', rpm_path,
                                   '-d', outdir,
                                   '-k', kernel_ver],
                                  stderr=subprocess.STDOUT).decode('utf-8')
    return out


def listfiles(dirname):
    return set(os.path.join(root, f)
               for root, dirs, files in os.walk(dirname)
               for f in files)


# helpers for creating RPMs to test with
@contextmanager
def in_tempdir(prefix='tmp'):
    oldcwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    os.chdir(tmpdir)
    yield
    os.chdir(oldcwd)
    shutil.rmtree(tmpdir)


def make_rpm(outdir, name='test', version='1.0', release='1', arch=None,
             for_anaconda_ver=None, for_kernel_ver=None,
             payload=None):
    """Create RPM for tests by using rpmfluff library."""
    p = SimpleRpmBuild(name, version, release)
    if for_anaconda_ver:
        p.add_provides('installer-enhancement = %s' % for_anaconda_ver)
    if for_kernel_ver:
        p.add_provides('kernel-modules >= %s' % for_kernel_ver)
    if payload is None:
        payload = []
    for item in payload:
        p.add_installed_file(item.path,
                             item.create_source_file(),
                             **item.kwargs)
    with in_tempdir("anaconda-test-dd."):
        with shutup():
            p.make()
        rpmfile = p.get_built_rpm(arch or expectedArch)
        outfile = os.path.join(outdir, os.path.basename(rpmfile))
        shutil.move(rpmfile, outfile)
    return p


class RPMFile(ABC):
    """Base class for simple container object for information about RPM payloads"""
    def __init__(self, path, srcpath=None, mode=None):
        self.path = path
        self.srcpath = srcpath or os.path.basename(path)
        self.kwargs = {}

        if mode:
            self.kwargs["mode"] = mode

    def create_source_file(self):
        """Create source file for RPM fluff."""
        pass


class TextRPMFile(RPMFile):
    """RPM file with text content"""
    def __init__(self, contents='', **kwargs):
        super().__init__(**kwargs)
        self.contents = contents

    def create_source_file(self):
        return SourceFile(self.srcpath, self.contents)


class BinRPMFile(RPMFile):
    """RPM file with binary content"""
    def create_source_file(self):
        return GeneratedSourceFile(self.srcpath, make_elf())


binfile = BinRPMFile(
    path="/usr/bin/fun",
    mode="0755"
)
libfile = BinRPMFile(
    path="/usr/lib/fun.so",
    mode="0755"
)
fwfile = TextRPMFile(
    path="/lib/firmware/fun.fw",
    contents="HELLO I AM FIRMWARE"
)
kofile = TextRPMFile(
    path="/lib/modules/KERNELVER/extra/net/fun.ko",
    contents="KERNEL MODULE??? YOU BETCHA"
)


# Finally, the actual test cases
class ASelfTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dd_tests.")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def rpmfluff_simple_test(self):
        """check if rpmfluff is working"""
        p = make_rpm(outdir=self.tmpdir)
        rpmfile = os.path.basename(p.get_built_rpm(expectedArch))
        self.assertTrue(rpmfile in os.listdir(self.tmpdir))

    def rpmfluff_payload_test(self):
        """check if rpmfluff can add files to built RPMs"""
        p = make_rpm(outdir=self.tmpdir, payload=(binfile, kofile))
        rpmfile = os.path.basename(p.get_built_rpm(expectedArch))
        self.assertTrue(rpmfile in os.listdir(self.tmpdir))

    def utils_exist_test(self):
        """check that the dd utilities exist"""
        self.assertTrue("dd_list" in os.listdir(UTILDIR))
        self.assertTrue("dd_extract" in os.listdir(UTILDIR))


class DD_List_TestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dd_tests.")
        self.k_ver = "4.1.4-333"
        self.a_ver = "22.0"

    def dd_list(self, dd_dir=None, kernel_ver=None, anaconda_ver=None):
        return dd_list(dd_dir or self.tmpdir,
                       kernel_ver or self.k_ver,
                       anaconda_ver or self.a_ver)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def dd_list_test(self):
        """dd_list: check output format"""
        rpm = make_rpm(self.tmpdir, for_kernel_ver=self.k_ver)
        drivers = self.dd_list()
        self.assertEqual(len(drivers), 1)
        d = drivers[0]
        self.assertEqual(d.name, rpm.name)
        self.assertEqual(d.description, rpm.basePackage.description)
        self.assertTrue(d.description)
        self.assertTrue(os.path.exists(d.source))
        self.assertIn("modules", d.flags)
        self.assertIn("firmwares", d.flags)
        self.assertNotIn("binaries", d.flags)
        self.assertNotIn("libraries", d.flags)

    def dd_list_multiple_test(self):
        """dd_list: multiple outputs for multiple packages"""
        names = ['fun', 'even_more_fun', 'too_much_fun']
        for name in names:
            make_rpm(self.tmpdir, name=name, for_kernel_ver=self.k_ver)
        drivers = self.dd_list()
        self.assertEqual(len(drivers), len(names))
        self.assertEqual(set(d.name for d in drivers), set(names))

    def dd_list_binaries_test(self):
        """dd_list: 'Provides:installer-enhancement' implies bins/libs"""
        make_rpm(self.tmpdir, for_anaconda_ver=self.a_ver)
        drivers = self.dd_list()
        self.assertFalse(drivers == [])
        d = drivers[0]
        self.assertIn("binaries", d.flags)
        self.assertIn("libraries", d.flags)
        self.assertNotIn("modules", d.flags)
        self.assertNotIn("firmwares", d.flags)

    def dd_list_old_kmods_test(self):
        """dd_list: ignore kmods if our kernel is too old"""
        make_rpm(self.tmpdir, for_kernel_ver="5.0.1-555")
        self.assertEqual(self.dd_list(), [])

    def dd_list_z_stream_kmods_test(self):
        """dd_list: accept kmods for z-stream kernels (#1207831)"""
        make_rpm(self.tmpdir, for_kernel_ver=self.k_ver)
        drivers = self.dd_list(kernel_ver=self.k_ver+".3")
        self.assertNotEqual(drivers, [])
        d = drivers[0]
        self.assertIn("modules", d.flags)

    def dd_list_anaconda_old_test(self):
        """dd_list: ignore installer-enhancements if version doesn't match"""
        make_rpm(self.tmpdir, for_anaconda_ver="23.0")
        self.assertEqual(self.dd_list(), [])

    def dd_list_no_rpms_test(self):
        """dd_list: empty directory returns no results"""
        self.assertEqual(self.dd_list(), [])

    def dd_list_missing_dir_test(self):
        """dd_list: missing directory returns no results"""
        self.assertEqual(self.dd_list(dd_dir="/non/existent/path"), [])


class DD_Extract_TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.k_ver = "4.1.4-333"
        cls.a_ver = "22.0"
        cls.tmpdir = tempfile.mkdtemp(prefix="dd_tests.")
        cls.rpmpayload = (binfile, kofile, fwfile, libfile)
        make_rpm(cls.tmpdir, payload=cls.rpmpayload)
        (cls.rpmfile,) = listfiles(cls.tmpdir)

    def setUp(self):
        self.outdir = os.path.join(self.tmpdir, "outdir")
        os.mkdir(self.outdir)

    def dd_extract(self, flags='-bmlf'):
        dd_extract(self.rpmfile, self.outdir, self.k_ver, flags=flags)
        return listfiles(self.outdir)

    def tearDown(self):
        shutil.rmtree(self.outdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir)

    def dd_extract_test(self):
        """dd_extract: files are extracted correctly"""
        self.dd_extract()
        for item in self.rpmpayload:
            out_path = self.outdir+item.path
            if isinstance(item, TextRPMFile):
                with open(out_path) as f:
                    self.assertEqual(item.contents, f.read())
            elif isinstance(item, BinRPMFile):
                self.assertTrue(os.path.exists(out_path))
                # check that file have some generated content
                self.assertGreater(os.stat(out_path).st_size, 1)

    def dd_extract_chmod_test(self):
        """dd_extract: files get correct mode (#1222056)"""
        self.dd_extract()
        for f in self.rpmpayload:
            # test only files which have file mode explicitly set
            if 'mode' in f.kwargs:
                binmode = os.stat(self.outdir+f.path).st_mode
                expectmode = int(f.kwargs['mode'], 8)
                print("testing", f.path)
                self.assertEqual(binmode & expectmode, expectmode)

    def dd_extract_modules_test(self):
        """dd_extract: using --modules extracts only .ko files"""
        outfiles = self.dd_extract(flags='--modules')
        self.assertEqual(outfiles, set([self.outdir+kofile.path]))

    def dd_extract_binaries_test(self):
        """dd_extract: using --binaries extracts only /bin, /sbin, etc."""
        outfiles = self.dd_extract(flags='--binaries')
        self.assertEqual(outfiles, set([self.outdir+binfile.path]))

    def dd_extract_libs_test(self):
        """dd_extract: using --libraries extracts only /lib etc."""
        outfiles = self.dd_extract(flags='--libraries')
        self.assertEqual(outfiles, set([self.outdir+libfile.path]))

    def dd_extract_firmware_test(self):
        """dd_extract: using --firmwares extracts only /lib/firmware"""
        outfiles = self.dd_extract(flags='--firmwares')
        self.assertEqual(outfiles, set([self.outdir+fwfile.path]))
