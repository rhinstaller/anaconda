/*
 * devices.h: handle declaration of devices to be created under /dev
 *
 * Copyright 2004 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#ifndef LOADER_INIT_DEVICES_H
#define LOADER_INIT_DEVICES_H

struct devnode {
    char * devname;
    int type;
    int major;
    int minor;
    int perms;
    char * owner;
    char * group;
};

#define CHARDEV 0
#define BLOCKDEV 1
#define DIRTYPE 2

struct devnode devnodes[] = {
    /* consoles */
    {"console", CHARDEV, 5, 1, 0600, "root", "root"},
    {"ttyS0", CHARDEV, 4, 64, 0600, "root", "root"},
    {"ttyS1", CHARDEV, 4, 65, 0600, "root", "root"},
    {"ttyS2", CHARDEV, 4, 66, 0600, "root", "root"},
    {"ttyS3", CHARDEV, 4, 67, 0600, "root", "root"},
#ifdef __ia64__
    {"ttySG0", CHARDEV, 204, 40, 0600, "root", "root"},
#endif
#ifdef __powerpc__
    {"hvsi0", CHARDEV, 229, 128, 0600, "root", "root"},
    {"hvsi1", CHARDEV, 229, 129, 0600, "root", "root"},
    {"hvsi2", CHARDEV, 229, 130, 0600, "root", "root"},
    {"hvc0", CHARDEV, 229, 0, 0600, "root", "root"},
#endif
#if defined(__i386__) || defined(__x86_64__) || defined(__ia64__)
    {"xvc0", CHARDEV, 204, 191, 0600, "root", "root"},
#endif
    /* base unix */
    {"null", CHARDEV, 1, 3, 0666, "root", "root"},
    {"zero", CHARDEV, 1, 5, 0666, "root", "root"},
    {"mem", CHARDEV, 1, 1, 0600, "root", "root"},
    /* ttys */
    {"pts", DIRTYPE, 0, 0, 0755, "root", "root"},
    {"ptmx", CHARDEV, 5, 2, 0666, "root", "root"},
    {"tty", CHARDEV, 5, 0, 0666, "root", "root"},
    {"tty0", CHARDEV, 4, 0, 0600, "root", "tty"},
    {"tty1", CHARDEV, 4, 1, 0600, "root", "tty"},
    {"tty2", CHARDEV, 4, 2, 0600, "root", "tty"},
    {"tty3", CHARDEV, 4, 3, 0600, "root", "tty"},
    {"tty4", CHARDEV, 4, 4, 0600, "root", "tty"},
    {"tty5", CHARDEV, 4, 5, 0600, "root", "tty"},
    {"tty6", CHARDEV, 4, 6, 0600, "root", "tty"},
    {"tty7", CHARDEV, 4, 7, 0600, "root", "tty"},
    {"tty8", CHARDEV, 4, 8, 0600, "root", "tty"},
    {"tty9", CHARDEV, 4, 9, 0600, "root", "tty"},
    /* fb */
    {"fb0", CHARDEV, 29, 0, 0600, "root", "tty"},
    /* sparc specific */
#ifdef __sparc__
    {"openprom", CHARDEV, 10, 139, 0644, "root", "root"},
    {"sunmouse", CHARDEV, 10, 6, 0644, "root", "root"},
    {"kbd", CHARDEV, 11, 0, 0644, "root", "root"},
#endif
    /* X */
    {"agpgart", CHARDEV, 10, 175, 0664, "root", "root"},
    {"psaux", CHARDEV, 10, 1, 0644, "root", "root"},
    {"input", DIRTYPE, 0, 0, 0755, "root", "root"},
    {"input/mice", CHARDEV, 13, 63, 0664, "root", "root"},
    /* floppies */
    {"fd0", BLOCKDEV, 2, 0, 0644, "root", "root"},
    {"fd1", BLOCKDEV, 2, 1, 0644, "root", "root"},
    /* random */
    {"random", CHARDEV, 1, 8, 0644, "root", "root"},
    {"urandom", CHARDEV, 1, 9, 0644, "root", "root"},
    /* mac stuff */
#ifdef __powerpc__
    {"nvram", CHARDEV, 10, 144, 0644, "root", "root"},
    {"adb", CHARDEV, 56, 0, 0644, "root", "root"},
    {"iseries", DIRTYPE, 0, 0, 0755, "root", "root" },
#endif
#ifdef __ia64__
    {"efirtc", CHARDEV, 10, 136, 0644, "root", "root"},
#endif
    {"rtc", CHARDEV, 10, 135, 0644, "root", "root"},
    { NULL, 0, 0, 0, 0, NULL, NULL },
};

#endif
