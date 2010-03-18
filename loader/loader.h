/*
 * loader.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdint.h>

#ifndef LOADER_H
#define LOADER_H

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_NOOP 2
#define LOADER_ERROR -1

/* #0 unused */
/* #1 unused */
#define LOADER_FLAGS_TEXT               (((uint64_t) 1) << 2)
#define LOADER_FLAGS_RESCUE             (((uint64_t) 1) << 3)
#define LOADER_FLAGS_KICKSTART          (((uint64_t) 1) << 4)
#define LOADER_FLAGS_KICKSTART_SEND_MAC (((uint64_t) 1) << 5)
#define LOADER_FLAGS_POWEROFF           (((uint64_t) 1) << 6)
#define LOADER_FLAGS_NOPROBE              (((uint64_t) 1) << 7)
#define LOADER_FLAGS_MODDISK            (((uint64_t) 1) << 8)
#define LOADER_FLAGS_EARLY_NETWORKING   (((uint64_t) 1) << 9)
#define LOADER_FLAGS_SERIAL             (((uint64_t) 1) << 10)
#define LOADER_FLAGS_UPDATES            (((uint64_t) 1) << 11)
#define LOADER_FLAGS_KSFILE             (((uint64_t) 1) << 12)
#define LOADER_FLAGS_HALT               (((uint64_t) 1) << 13)
#define LOADER_FLAGS_SELINUX            (((uint64_t) 1) << 14)
#define LOADER_FLAGS_VIRTPCONSOLE       (((uint64_t) 1) << 15)
/* #16 unused */
#define LOADER_FLAGS_NOSHELL            (((uint64_t) 1) << 17)
/* #18 unused */
#define LOADER_FLAGS_TELNETD            (((uint64_t) 1) << 19)
#define LOADER_FLAGS_NOPASS             (((uint64_t) 1) << 20)
/* #21 unused */
#define LOADER_FLAGS_MEDIACHECK         (((uint64_t) 1) << 22)
/* #23 unused */
#define LOADER_FLAGS_ASKMETHOD          (((uint64_t) 1) << 24)
#define LOADER_FLAGS_ASKNETWORK         (((uint64_t) 1) << 25)
/* #26 unused */
/* #27 unused */
#define LOADER_FLAGS_CMDLINE            (((uint64_t) 1) << 28)
#define LOADER_FLAGS_GRAPHICAL          (((uint64_t) 1) << 29)
#define LOADER_FLAGS_NOIPV4             (((uint64_t) 1) << 31)
#ifdef ENABLE_IPV6
#define LOADER_FLAGS_NOIPV6             (((uint64_t) 1) << 32)
#endif
#define LOADER_FLAGS_IP_PARAM           (((uint64_t) 1) << 33)
#ifdef ENABLE_IPV6
#define LOADER_FLAGS_IPV6_PARAM         (((uint64_t) 1) << 34)
#endif
#define LOADER_FLAGS_IS_KICKSTART       (((uint64_t) 1) << 35)
#define LOADER_FLAGS_ALLOW_WIRELESS     (((uint64_t) 1) << 36)
#define LOADER_FLAGS_HAVE_CMSCONF       (((uint64_t) 1) << 37)
#define LOADER_FLAGS_NOKILL		(((uint64_t) 1) << 38)
#define LOADER_FLAGS_KICKSTART_SEND_SERIAL   (((uint64_t) 1) << 39)
#define LOADER_FLAGS_AUTOMODDISK        (((uint64_t) 1) << 40)

#define FL_TEXT(a)               ((a) & LOADER_FLAGS_TEXT)
#define FL_RESCUE(a)             ((a) & LOADER_FLAGS_RESCUE)
#define FL_KICKSTART(a)          ((a) & LOADER_FLAGS_KICKSTART)
#define FL_KICKSTART_SEND_MAC(a) ((a) & LOADER_FLAGS_KICKSTART_SEND_MAC)
#define FL_POWEROFF(a)           ((a) & LOADER_FLAGS_POWEROFF)
#define FL_NOPROBE(a)            ((a) & LOADER_FLAGS_NOPROBE)
#define FL_MODDISK(a)            ((a) & LOADER_FLAGS_MODDISK)
#define FL_EARLY_NETWORKING(a)   ((a) & LOADER_FLAGS_EARLY_NETWORKING)
#define FL_SERIAL(a)             ((a) & LOADER_FLAGS_SERIAL)
#define FL_UPDATES(a)            ((a) & LOADER_FLAGS_UPDATES)
#define FL_KSFILE(a)             ((a) & LOADER_FLAGS_KSFILE)
#define FL_NOSHELL(a)            ((a) & LOADER_FLAGS_NOSHELL)
#define FL_TELNETD(a)            ((a) & LOADER_FLAGS_TELNETD)
#define FL_NOPASS(a)             ((a) & LOADER_FLAGS_NOPASS)
#define FL_MEDIACHECK(a)         ((a) & LOADER_FLAGS_MEDIACHECK)
#define FL_ASKMETHOD(a)          ((a) & LOADER_FLAGS_ASKMETHOD)
#define FL_GRAPHICAL(a)          ((a) & LOADER_FLAGS_GRAPHICAL)
#define FL_CMDLINE(a)            ((a) & LOADER_FLAGS_CMDLINE)
#define FL_HALT(a)               ((a) & LOADER_FLAGS_HALT)
#define FL_SELINUX(a)            ((a) & LOADER_FLAGS_SELINUX)
#define FL_VIRTPCONSOLE(a)       ((a) & LOADER_FLAGS_VIRTPCONSOLE)
#define FL_ASKNETWORK(a)         ((a) & LOADER_FLAGS_ASKNETWORK)
#define FL_NOIPV4(a)             ((a) & LOADER_FLAGS_NOIPV4)
#ifdef ENABLE_IPV6
#define FL_NOIPV6(a)             ((a) & LOADER_FLAGS_NOIPV6)
#endif
#define FL_IP_PARAM(a)           ((a) & LOADER_FLAGS_IP_PARAM)
#ifdef ENABLE_IPV6
#define FL_IPV6_PARAM(a)         ((a) & LOADER_FLAGS_IPV6_PARAM)
#endif
#define FL_IS_KICKSTART(a)       ((a) & LOADER_FLAGS_IS_KICKSTART)
#define FL_ALLOW_WIRELESS(a)     ((a) & LOADER_FLAGS_ALLOW_WIRELESS)
#define FL_HAVE_CMSCONF(a)       ((a) & LOADER_FLAGS_HAVE_CMSCONF)
#define FL_NOKILL(a)		 ((a) & LOADER_FLAGS_NOKILL)
#define FL_KICKSTART_SEND_SERIAL(a) ((a) & LOADER_FLAGS_KICKSTART_SEND_SERIAL)
#define FL_AUTOMODDISK(a)        ((a) & LOADER_FLAGS_AUTOMODDISK)

void startNewt(void);
void stopNewt(void);
char * getProductName(void);
char * getProductPath(void);
char * getProductArch(void);

#include "moduleinfo.h"
#include "../isys/devices.h"
/* JKFIXME: I don't like all of the _set attribs, but without them,
 * we can't tell if it was explicitly set by kickstart/cmdline or 
 * if we just got it going through the install.   */
struct loaderData_s {
    char * lang;
    int lang_set;
    char * kbd;
    int kbd_set;
    char * netDev;
    int netDev_set;
    char * bootIf;
    int bootIf_set;
    char * netCls;
    int netCls_set;
    char *ipv4, *netmask, *gateway, *dns, *hostname, *peerid, *ethtool, *subchannels, *portname, *essid, *wepkey, *nettype, *ctcprot, *layer2, *portno, *macaddr;
#ifdef ENABLE_IPV6
    char *ipv6;
    int ipv6info_set;
    char *gateway6;
#endif
    int mtu;
    int noDns;
    int dhcpTimeout;
    int ipinfo_set;
    char * ksFile;
    int method;
    char * ddsrc;
    void * stage2Data;
    char * logLevel;
    char * updatessrc;
    char * dogtailurl;
    char * gdbServer;
    char * instRepo;

    pid_t fw_loader_pid;
    char *fw_search_pathz;
    size_t fw_search_pathz_len;

    moduleInfoSet modInfo;

    int inferredStage2, invalidRepoParam;

    /* Proxy info needs to be in the loaderData so we can get these
     * settings off the command line, too.
     */
    char *proxy;
    char *proxyUser;
    char *proxyPassword;
};

/* 64 bit platforms, definitions courtesy of glib */
#if defined (__x86_64__) || defined(__ia64__) || defined(__alpha__) || defined(__powerpc64__) || defined(__s390x__) || (defined(__sparc__) && defined(__arch64__))
#define POINTER_TO_INT(p)  ((int) (long) (p))
#define INT_TO_POINTER(i)  ((void *) (long) (i))
#else
#define POINTER_TO_INT(p)  ((int) (p))
#define INT_TO_POINTER(i)  ((void *) (i))
#endif

/* library paths */
#if defined(__x86_64__) || defined(__s390x__) || defined(__powerpc64__)
#define LIBPATH "/lib64:/usr/lib64:/usr/X11R6/lib64:/usr/kerberos/lib64:/mnt/usr/lib64:/mnt/sysimage/lib64:/mnt/sysimage/usr/lib64"
#else
#define LIBPATH "/lib:/usr/lib:/usr/X11R6/lib:/usr/kerberos/lib:/mnt/usr/lib:/mnt/sysimage/lib:/mnt/sysimage/usr/lib"
#endif

#define checked_asprintf(...)                                       \
    if (asprintf( __VA_ARGS__ ) == -1) {                            \
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);     \
        abort();                                                    \
    }

#endif
