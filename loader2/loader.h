#include <stdint.h>

#ifndef LOADER_H
#define LOADER_H

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_NOOP 2
#define LOADER_ERROR -1

#define GUI_STAGE2_RAM 294912

#define LOADER_FLAGS_TESTING            (((uint64_t) 1) << 0)
#define LOADER_FLAGS_EXPERT             (((uint64_t) 1) << 1)
#define LOADER_FLAGS_TEXT               (((uint64_t) 1) << 2)
#define LOADER_FLAGS_RESCUE             (((uint64_t) 1) << 3)
#define LOADER_FLAGS_KICKSTART          (((uint64_t) 1) << 4)
#define LOADER_FLAGS_KICKSTART_SEND_MAC (((uint64_t) 1) << 5)
#define LOADER_FLAGS_POWEROFF           (((uint64_t) 1) << 6)
#define LOADER_FLAGS_NONET              (((uint64_t) 1) << 7)
#define LOADER_FLAGS_MODDISK            (((uint64_t) 1) << 8)
#define LOADER_FLAGS_ISA                (((uint64_t) 1) << 9)
#define LOADER_FLAGS_SERIAL             (((uint64_t) 1) << 10)
#define LOADER_FLAGS_UPDATES            (((uint64_t) 1) << 11)
#define LOADER_FLAGS_KSFILE             (((uint64_t) 1) << 12)
#define LOADER_FLAGS_HALT               (((uint64_t) 1) << 13)
#define LOADER_FLAGS_SELINUX            (((uint64_t) 1) << 14)
#define LOADER_FLAGS_VIRTPCONSOLE       (((uint64_t) 1) << 15)
#define LOADER_FLAGS_NOUSB              (((uint64_t) 1) << 16)
#define LOADER_FLAGS_NOSHELL            (((uint64_t) 1) << 17)
#define LOADER_FLAGS_NOPCMCIA           (((uint64_t) 1) << 18)
#define LOADER_FLAGS_TELNETD            (((uint64_t) 1) << 19)
#define LOADER_FLAGS_NOPASS             (((uint64_t) 1) << 20)
#define LOADER_FLAGS_UB                 (((uint64_t) 1) << 21)
#define LOADER_FLAGS_MEDIACHECK         (((uint64_t) 1) << 22)
#define LOADER_FLAGS_NOUSBSTORAGE       (((uint64_t) 1) << 23)
#define LOADER_FLAGS_ASKMETHOD          (((uint64_t) 1) << 24)
#define LOADER_FLAGS_ASKNETWORK         (((uint64_t) 1) << 25)
#define LOADER_FLAGS_NOIEEE1394         (((uint64_t) 1) << 26)
#define LOADER_FLAGS_NOFB               (((uint64_t) 1) << 27)
#define LOADER_FLAGS_CMDLINE            (((uint64_t) 1) << 28)
#define LOADER_FLAGS_GRAPHICAL          (((uint64_t) 1) << 29)
#define LOADER_FLAGS_NOSTORAGE          (((uint64_t) 1) << 30)
#define LOADER_FLAGS_NOIPV4             (((uint64_t) 1) << 31)
#define LOADER_FLAGS_NOIPV6             (((uint64_t) 1) << 32)
#define LOADER_FLAGS_IP_PARAM           (((uint64_t) 1) << 33)
#define LOADER_FLAGS_IPV6_PARAM         (((uint64_t) 1) << 34)
#define LOADER_FLAGS_IS_KICKSTART       (((uint64_t) 1) << 35)
#define LOADER_FLAGS_HAVE_CMSCONF       (((uint64_t) 1) << 36)
#define LOADER_FLAGS_AUTOMODDISK        (((uint64_t) 1) << 37)
#define LOADER_FLAGS_NOEJECT            (((uint64_t) 1) << 38)

#define FL_TESTING(a)            ((a) & LOADER_FLAGS_TESTING)
#define FL_EXPERT(a)             ((a) & LOADER_FLAGS_EXPERT)
#define FL_TEXT(a)               ((a) & LOADER_FLAGS_TEXT)
#define FL_RESCUE(a)             ((a) & LOADER_FLAGS_RESCUE)
#define FL_KICKSTART(a)          ((a) & LOADER_FLAGS_KICKSTART)
#define FL_KICKSTART_SEND_MAC(a) ((a) & LOADER_FLAGS_KICKSTART_SEND_MAC)
#define FL_POWEROFF(a)           ((a) & LOADER_FLAGS_POWEROFF)
#define FL_NONET(a)              ((a) & LOADER_FLAGS_NONET)
#define FL_MODDISK(a)            ((a) & LOADER_FLAGS_MODDISK)
#define FL_ISA(a)                ((a) & LOADER_FLAGS_ISA)
#define FL_SERIAL(a)             ((a) & LOADER_FLAGS_SERIAL)
#define FL_UPDATES(a)            ((a) & LOADER_FLAGS_UPDATES)
#define FL_KSFILE(a)             ((a) & LOADER_FLAGS_KSFILE)
#define FL_NOUSB(a)              ((a) & LOADER_FLAGS_NOUSB)
#define FL_NOSHELL(a)            ((a) & LOADER_FLAGS_NOSHELL)
#define FL_NOFB(a)               ((a) & LOADER_FLAGS_NOFB)
#define FL_NOPCMCIA(a)           ((a) & LOADER_FLAGS_NOPCMCIA)
#define FL_RESCUE_NOMOUNT(a)     ((a) & LOADER_FLAGS_RESCUE_NOMOUNT)
#define FL_TELNETD(a)            ((a) & LOADER_FLAGS_TELNETD)
#define FL_NOPASS(a)             ((a) & LOADER_FLAGS_NOPASS)
#define FL_MEDIACHECK(a)         ((a) & LOADER_FLAGS_MEDIACHECK)
#define FL_NOUSBSTORAGE(a)       ((a) & LOADER_FLAGS_NOUSBSTORAGE)
#define FL_ASKMETHOD(a)          ((a) & LOADER_FLAGS_ASKMETHOD)
#define FL_NOPARPORT(a)          ((a) & LOADER_FLAGS_NOPARPORT)
#define FL_NOIEEE1394(a)         ((a) & LOADER_FLAGS_NOIEEE1394)
#define FL_NOFB(a)               ((a) & LOADER_FLAGS_NOFB)
#define FL_GRAPHICAL(a)          ((a) & LOADER_FLAGS_GRAPHICAL)
#define FL_CMDLINE(a)            ((a) & LOADER_FLAGS_CMDLINE)
#define FL_HALT(a)               ((a) & LOADER_FLAGS_HALT)
#define FL_SELINUX(a)            ((a) & LOADER_FLAGS_SELINUX)
#define FL_VIRTPCONSOLE(a)       ((a) & LOADER_FLAGS_VIRTPCONSOLE)
#define FL_NOSTORAGE(a)          ((a) & LOADER_FLAGS_NOSTORAGE)
#define FL_NOPROBE(a)            (FL_NOSTORAGE((a)) | FL_NONET((a)))
#define FL_ASKNETWORK(a)         ((a) & LOADER_FLAGS_ASKNETWORK)
#define FL_UB(a)                 ((a) & LOADER_FLAGS_UB)
#define FL_NOIPV4(a)             ((a) & LOADER_FLAGS_NOIPV4)
#define FL_NOIPV6(a)             ((a) & LOADER_FLAGS_NOIPV6)
#define FL_IP_PARAM(a)           ((a) & LOADER_FLAGS_IP_PARAM)
#define FL_IPV6_PARAM(a)         ((a) & LOADER_FLAGS_IPV6_PARAM)
#define FL_IS_KICKSTART(a)       ((a) & LOADER_FLAGS_IS_KICKSTART)
#define FL_HAVE_CMSCONF(a)       ((a) & LOADER_FLAGS_HAVE_CMSCONF)
#define FL_AUTOMODDISK(a)        ((a) & LOADER_FLAGS_AUTOMODDISK)
#define FL_NOEJECT(a)            ((a) & LOADER_FLAGS_NOEJECT)

void startNewt(void);
void stopNewt(void);
char * getProductName(void);
char * getProductPath(void);

#include "modules.h"
#include "moduledeps.h"
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
    char *ip, *ipv6, *netmask, *gateway, *dns, *hostname, *peerid, *ethtool, *subchannels, *portname, *essid, *wepkey, *nettype, *ctcprot, *layer2, *portno, *macaddr;
    int mtu;
    int noDns;
    int dhcpTimeout;
    int ipinfo_set;
    int ipv6info_set;
    char * ksFile;
    int method;
    char * ddsrc;
    void * methodData;
    char * logLevel;
    char * updatessrc;

    pid_t fw_loader_pid;
    char *fw_search_pathz;
    size_t fw_search_pathz_len;

    moduleList modLoaded;
    moduleDeps * modDepsPtr;
    moduleInfoSet modInfo;
};

/* 64 bit platforms, definitions courtesy of glib */
#if defined (__x86_64__) || defined(__ia64__) || defined(__alpha__) || defined(__powerpc64__) || defined(__sparc64__) || defined(__s390x__)
#define POINTER_TO_INT(p)  ((int) (long) (p))
#define INT_TO_POINTER(i)  ((void *) (long) (i))
#else
#define POINTER_TO_INT(p)  ((int) (p))
#define INT_TO_POINTER(i)  ((void *) (i))
#endif

/* library paths */
#if defined(__x86_64__) || defined(__s390x__) || defined(__ppc64__)
#define LIBPATH "/lib64:/usr/lib64:/usr/X11R6/lib64:/usr/kerberos/lib64:/mnt/usr/lib64:/mnt/sysimage/lib64:/mnt/sysimage/usr/lib64"
#else
#define LIBPATH "/lib:/usr/lib:/usr/X11R6/lib:/usr/kerberos/lib:/mnt/usr/lib:/mnt/sysimage/lib:/mnt/sysimage/usr/lib"
#endif

#endif
