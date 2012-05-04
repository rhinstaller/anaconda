# configure.ac for anaconda
#
# Copyright (C) 2009  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: David Cantrell <dcantrell@redhat.com>

m4_define(python_required_version, 2.5)

AC_PREREQ([2.63])
AC_INIT([anaconda], [17.24], [anaconda-devel-list@redhat.com])
AM_INIT_AUTOMAKE([foreign no-dist-gzip dist-bzip2])

AC_CONFIG_HEADERS([config.h])
AC_CONFIG_MACRO_DIR([m4])

AC_DEFINE_UNQUOTED([BUILD_DATE], ["`date +%m%d%Y`"], [Date of anaconda build])
AM_SILENT_RULES([yes]) # make --enable-silent-rules the default.

# Checks for programs.
AC_PROG_AWK
AC_PROG_GREP
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_MAKE_SET
AC_PROG_LIBTOOL

AM_GNU_GETTEXT([external])

# Checks for libraries.
AC_CHECK_LIB([X11], [XGetWindowAttributes],
             [AC_SUBST(X11_LIBS, [-lX11])],
             [AC_MSG_FAILURE([*** libX11 not usable.])])

AC_CHECK_LIB([audit], [audit_open],
             [AC_SUBST(AUDIT_LIBS, [-laudit])],
             [AC_MSG_FAILURE([*** libaudit not usable.])])

AC_CHECK_LIB([blkid], [blkid_get_cache],
             [AC_SUBST(BLKID_LIBS, [-lblkid])],
             [AC_MSG_FAILURE([*** libblkid not usable.])])

AC_CHECK_LIB([checkisomd5], [mediaCheckFile],
             [AC_SUBST(CHECKISOMD5_LIBS, [-lcheckisomd5])],
             [AC_MSG_FAILURE([*** libcheckisomd5 not usable.])])

AC_CHECK_LIB([ext2fs], [ext2fs_initialize],
             [AC_SUBST(EXT2FS_LIBS, [-lext2fs])],
             [AC_MSG_FAILURE([*** libext2fs not usable.])])

AC_CHECK_LIB([iscsi], [libiscsi_get_firmware_network_config],
             [AC_SUBST(ISCSI_LIBS, [-liscsi])],
             [AC_MSG_FAILURE([*** libiscsi not usable.])])

AC_CHECK_LIB([newt], [newtInit],
             [AC_SUBST(NEWT_LIBS, [-lnewt])],
             [AC_MSG_FAILURE([*** libnewt not usable.])])

AC_CHECK_LIB([slang], [SLang_get_int_size],
             [AC_SUBST(SLANG_LIBS, [-lslang])],
             [AC_MSG_FAILURE([*** libslang not usable.])])

AC_CHECK_LIB([z], [zlibVersion],
             [AC_SUBST(ZLIB_LIBS, [-lz])],
             [AC_MSG_FAILURE([*** libz not usable.])])

# Checks for header files.
AC_PATH_X
AC_FUNC_ALLOCA
AC_HEADER_RESOLV
AC_HEADER_MAJOR
AC_CHECK_HEADERS([argz.h arpa/inet.h fcntl.h inttypes.h libintl.h limits.h \
                  malloc.h netdb.h netinet/in.h stddef.h stdint.h stdlib.h \
                  string.h strings.h sys/ioctl.h sys/mount.h sys/param.h \
                  sys/socket.h sys/time.h sys/vfs.h syslog.h termios.h \
                  unistd.h utime.h wchar.h],
                 [],
                 [AC_MSG_FAILURE([*** Header file $ac_header not found.])],
                 [])

# Checks for typedefs, structures, and compiler characteristics.
AC_TYPE_UID_T
AC_C_INLINE
AC_TYPE_INT32_T
AC_TYPE_MODE_T
AC_TYPE_OFF_T
AC_TYPE_PID_T
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_CHECK_MEMBERS([struct stat.st_rdev])
AC_TYPE_UINT16_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_UINT8_T

# Checks for library functions.
AC_FUNC_CHOWN
AC_FUNC_ERROR_AT_LINE
AC_FUNC_FORK
AC_FUNC_LSTAT_FOLLOWS_SLASHED_SYMLINK
AC_FUNC_MALLOC
AC_FUNC_MMAP
AC_FUNC_REALLOC
AC_CHECK_FUNCS([dup2 fdatasync ftruncate getcwd gethostbyname gettimeofday \
                lchown memmove memset mkdir mkfifo munmap realpath select \
                setenv sethostname socket strcasecmp strchr strcspn strdup \
                strerror strncasecmp strndup strrchr strstr strtol strtoul \
                strverscmp uname utime wcwidth],
               [],
               [AC_MSG_FAILURE([*** Required function $ac_func not found.])])

AM_PATH_PYTHON(python_required_version)
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers or library)])

# Check for libraries we need that provide pkg-config scripts
PKG_PROG_PKG_CONFIG([0.23])
PKG_CHECK_MODULES([X11], [x11 >= 1.3])
PKG_CHECK_MODULES([XCOMPOSITE], [xcomposite >= 0.4.1])
PKG_CHECK_MODULES([GLIB], [glib-2.0 >= 2.16.1])
PKG_CHECK_MODULES([GTK_X11], [gtk+-x11-2.0 >= 2.16.1])
PKG_CHECK_MODULES([GDK], [gdk-2.0 >= 2.16.1])
PKG_CHECK_MODULES([NETWORKMANAGER], [NetworkManager >= 0.7.1])
PKG_CHECK_MODULES([LIBNL], [libnl-1 >= 1.0])
PKG_CHECK_MODULES([LIBNM_GLIB], [libnm-glib >= 0.7.1 libnm-util >= 0.7.1])
PKG_CHECK_MODULES([DEVMAPPER], [devmapper >= 1.02.17])
PKG_CHECK_MODULES([LIBCURL], [libcurl >= 7.19.5])
PKG_CHECK_MODULES([RPM], [rpm >= 4.8.0])
PKG_CHECK_MODULES([LIBARCHIVE], [libarchive >= 2.7.902a])

# Set $RPM_OPT_FLAGS if we don't have it
if test -z $RPM_OPT_FLAGS ; then
    CFLAGS="$CFLAGS -g -pipe -Wp,-D_FORTIFY_SOURCE=2 -fexceptions"
else
    CFLAGS="$CFLAGS $RPM_OPT_FLAGS"
fi

# SELinux support can be enabled or disabled
AC_ARG_ENABLE(selinux,
    AC_HELP_STRING([--enable-selinux],
                   [enable SELinux support (default is yes)]),
    [selinux=$enableval],
    [selinux=yes])
if test x$selinux = xyes ; then
    AC_CHECK_LIB([selinux], [matchpathcon], [],
        [AC_MSG_FAILURE([*** libselinux not usable.])])
    AC_CHECK_LIB([selinux], [lsetfilecon], [],
        [AC_MSG_FAILURE([*** libselinux not usable.])])

    selinux_libs="-lselinux -laudit"
    AC_SUBST(SELINUX_CFLAGS, [-DUSESELINUX=1])
    AC_SUBST(SELINUX_LIBS, [$selinux_libs])
fi

# NFS support can, in theory, be enabled or disabled
AC_ARG_ENABLE(nfs,
    AC_HELP_STRING([--enable-nfs],
                   [enable NFS support (default is yes)]),
    [nfs=$enableval],
    [nfs=yes])
if test x$selinux = xyes ; then
    AC_SUBST(NFS_CFLAGS, [-DHAVE_NFS])
fi

# IPv6 support can be enabled or disabled
AC_ARG_ENABLE(ipv6,
    AC_HELP_STRING([--enable-ipv6],
                   [enable IPv6 support (default is yes)]),
    [ipv6=$enableval],
    [ipv6=yes])
if test x$ipv6 = xyes ; then
    AC_SUBST(IPV6_CFLAGS, [-DENABLE_IPV6])
fi

# GCC likes to bomb out on some ridiculous warnings.  Add your favorites
# here.
SHUT_UP_GCC="-Wno-unused-result"

# Add remaining compiler flags we want to use
CFLAGS="$CFLAGS -Wall -Werror $SHUT_UP_GCC -D_GNU_SOURCE -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE"

# Filter CFLAGS (remove duplicate flags)
cflags_filter() {
    have=
    first=1
    for flag in $* ; do
        if test -z "`echo $have | grep -- $flag`" ; then
            if test x$first == x1 ; then
                first=2
            else
                echo -n " "
            fi
            echo -n $flag
            have="$have $flag"
        fi
    done
}
CFLAGS="`cflags_filter $CFLAGS`"

# Unset $(LIBS) because different programs and libraries will have different
# lists of libraries to link with, we don't want everything linking against
# all libraries we checked for.
LIBS=

# Get the release number from the spec file
rel="`awk '/Release:/ { split($2, r, "%"); print r[[1]] }' anaconda.spec.in`"
AC_SUBST(PACKAGE_RELEASE, [$rel])

# Set $(ARCH) and arch-related tests
s_arch="`uname -m | sed -e s/i.86/i386/ -e s/sparc.*/sparc/ -e s/ppc.*/ppc/`"
AC_SUBST(ARCH, [$s_arch])

AM_CONDITIONAL(IS_LIVEINST_ARCH,
  [test x$s_arch == xppc || test x$s_arch == xi386 || test x$s_arch == xx86_64])

AM_CONDITIONAL(IS_GPTSYNC_ARCH,
  [test x$s_arch == xi386 || test x$s_arch == xx86_64])

AM_CONDITIONAL(IS_KEYMAPS_OVERRIDE_ARCH,
  [test x$s_arch == xi386 || test x$s_arch == xppc || test x$s_arch == xx86_64])

AM_CONDITIONAL(IS_I386,
  [test x$s_arch == xi386])

AM_CONDITIONAL(IS_PPC,
  [test x$s_arch == xppc])

AM_CONDITIONAL(IS_S390,
  [test x$s_arch == xs390 || test x$s_arch == xs390x])

AM_CONDITIONAL(IS_X86_64,
  [test x$s_arch == xx86_64])

AM_CONDITIONAL(IS_SPARC,
  [test x$s_arch == xsparc || test x$s_arch == xsparc64])

AC_CONFIG_FILES([Makefile
                 data/Makefile
                 data/bootdisk/Makefile
                 data/bootdisk/i386/Makefile
                 data/bootdisk/ppc/Makefile
                 data/bootdisk/sparc/Makefile
                 data/bootdisk/s390x/Makefile
                 data/bootdisk/x86_64/Makefile
                 data/command-stubs/Makefile
                 docs/Makefile
                 dracut/Makefile
                 gptsync/Makefile
                 pyanaconda/installclasses/Makefile
                 pyanaconda/iw/Makefile
                 data/liveinst/Makefile
                 data/liveinst/console.apps/Makefile
                 data/liveinst/gnome/Makefile
                 data/liveinst/pam.d/Makefile
                 data/pixmaps/Makefile
                 data/icons/Makefile
                 data/icons/hicolor/Makefile
                 data/icons/hicolor/16x16/Makefile
                 data/icons/hicolor/16x16/apps/Makefile
                 data/icons/hicolor/22x22/Makefile
                 data/icons/hicolor/22x22/apps/Makefile
                 data/icons/hicolor/24x24/Makefile
                 data/icons/hicolor/24x24/apps/Makefile
                 data/icons/hicolor/32x32/Makefile
                 data/icons/hicolor/32x32/apps/Makefile
                 data/icons/hicolor/48x48/Makefile
                 data/icons/hicolor/48x48/apps/Makefile
                 data/icons/hicolor/256x256/Makefile
                 data/icons/hicolor/256x256/apps/Makefile
                 data/systemd/Makefile
                 po/Makefile.in
                 scripts/Makefile
                 pyanaconda/Makefile
                 pyanaconda/isys/Makefile
                 pyanaconda/storage/Makefile
                 pyanaconda/storage/devicelibs/Makefile
                 pyanaconda/storage/formats/Makefile
                 tests/Makefile
                 tests/mock/Makefile
                 tests/kickstart_test/Makefile
                 tests/storage_test/Makefile
                 tests/storage_test/devicelibs_test/Makefile
                 tests/pylint/Makefile
                 tests/regex/Makefile
                 tests/pyanaconda_test/Makefile
                 tests/logpicker_test/Makefile
                 tests/logpicker_test/sending_test/Makefile
                 tests/logpicker_test/archiving_test/Makefile
                 tests/logpicker_test/logmining_test/Makefile
                 pyanaconda/textw/Makefile
                 data/ui/Makefile
                 utils/Makefile
                 utils/log_picker/Makefile
                 utils/log_picker/sending/Makefile])
AC_OUTPUT
