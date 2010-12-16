/*
 * loader.c
 *
 * This is the installer loader.  Its job is to somehow load the rest
 * of the installer into memory and run it.  This may require setting
 * up some devices and networking, etc. The main point of this code is
 * to stay SMALL! Remember that, live by that, and learn to like it.
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2006 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <ctype.h>
#include <errno.h>
#include <execinfo.h>
#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <syslog.h>
#include <unistd.h>
#include <stdint.h>

#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>

#include <linux/fb.h>
#include <linux/serial.h>
#include <linux/vt.h>

#ifdef USE_MTRACE
#include <mcheck.h>
#endif

#include "loader.h"
#include "loadermisc.h" /* JKFIXME: functions here should be split out */
#include "log.h"
#include "lang.h"
#include "fwloader.h"
#include "kbd.h"
#include "kickstart.h"
#include "windows.h"

/* module stuff */
#include "modules.h"
#include "moduleinfo.h"
#include "moduledeps.h"
#include "modstubs.h"

#include "getparts.h"
#include "driverdisk.h"

/* hardware stuff */
#include "hardware.h"
#include "firewire.h"
#include "pcmcia.h"
#include "usb.h"
#if !defined(__s390__) && !defined(__s390x__)
#include "ibft.h"
#endif

/* install method stuff */
#include "method.h"
#include "cdinstall.h"
#include "nfsinstall.h"
#include "hdinstall.h"
#include "urlinstall.h"

#include "net.h"
#include "telnetd.h"

#include <selinux/selinux.h>
#include "selinux.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/stubs.h"
#include "../isys/lang.h"
#include "../isys/eddsupport.h"
#include "../isys/str.h"

/* maximum number of extra arguments that can be passed to the second stage */
#define MAX_EXTRA_ARGS 128
static char * extraArgs[MAX_EXTRA_ARGS];
static int hasGraphicalOverride();

static int newtRunning = 0;

/* boot flags -- we need these in a lot of places */
uint64_t flags = LOADER_FLAGS_SELINUX | LOADER_FLAGS_NOFB;

#ifdef INCLUDE_LOCAL
#include "cdinstall.h"
#include "hdinstall.h"
#endif
#ifdef INCLUDE_NETWORK
#include "nfsinstall.h"
#include "urlinstall.h"
#endif

int num_link_checks = 5;
int post_link_sleep = 0;

static pid_t init_pid = 1;

static struct installMethod installMethods[] = {
    { N_("Local CDROM"), "cdrom", 0, CLASS_CDROM, mountCdromImage },
    { N_("Hard drive"), "hd", 0, CLASS_HD, mountHardDrive },
    { N_("NFS image"), "nfs", 1, CLASS_NETWORK, mountNfsImage },
    { "FTP", "ftp", 1, CLASS_NETWORK, mountUrlImage },
    { "HTTP", "http", 1, CLASS_NETWORK, mountUrlImage },
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

void setupRamfs(void) {
    mkdirChain("/tmp/ramfs");
    doPwMount("none", "/tmp/ramfs", "ramfs", 0, NULL);
}

void doSuspend(void) {
    newtFinished();
    exit(1);
}

void doShell(void) {
    /* this lets us debug the loader just by having a second initramfs
     * containing /sbin/busybox */
    int child, status;

    newtSuspend();
    if (!(child = fork())) {
	    execl("/sbin/busybox", "msh", NULL);
	    _exit(1);
    }
    waitpid(child, &status, 0);
    newtResume();
}

void startNewt(void) {
    if (!newtRunning) {
        char *buf = sdupprintf(_("Welcome to %s"), getProductName());
        newtInit();
        newtCls();
        newtDrawRootText(0, 0, buf);
        free(buf);
        
        newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
        
        newtRunning = 1;
        if (FL_TESTING(flags)) 
            newtSetSuspendCallback((void *) doSuspend, NULL);
        else if (!access("/sbin/busybox",  X_OK)) 
            newtSetSuspendCallback((void *) doShell, NULL);
    }
}

void stopNewt(void) {
    if (newtRunning) newtFinished();
    newtRunning = 0;
}

static char * productName = NULL;
static char * productPath = NULL;

static void initProductInfo(void) {
    FILE *f;
    int i;

    f = fopen("/.buildstamp", "r");
    if (!f) {
        productName = strdup("anaconda");
        productPath = strdup("anaconda");
    } else {
        productName = malloc(256);
        productPath = malloc(256);
        productName = fgets(productName, 256, f); /* stamp time */
        productName = fgets(productName, 256, f); /* product name */
        productPath = fgets(productPath, 256, f); /* product version */
        productPath = fgets(productPath, 256, f); /* product path */

        i = strlen(productName) - 1;
        while (isspace(*(productName + i))) {
            *(productName + i) = '\0';
            i--;
        }
        i = strlen(productPath) - 1;
        while (isspace(*(productPath + i))) {
            *(productPath + i) = '\0';
            i--;
        }
    }
}

char * getProductName(void) {
    if (!productName) {
       initProductInfo();
    }
    return productName;
}

char * getProductPath(void) {
    if (!productPath) {
       initProductInfo();
    }
    return productPath;
}

void initializeConsole(moduleList modLoaded, moduleDeps modDeps,
                       moduleInfoSet modInfo) {
    if (!FL_NOFB(flags))
        mlLoadModuleSet("vgastate:vga16fb", modLoaded, modDeps, modInfo);

    /* enable UTF-8 console */
    printf("\033%%G");
    fflush(stdout);

    isysLoadFont();
    if (!FL_TESTING(flags))
        isysSetUnicodeKeymap();
}

/* fbcon is buggy and resets our color palette if we allocate a terminal
 * after initializing it, so we initialize 9 of them before we need them.
 * If it doesn't work, the user gets to suffer through having an ugly palette,
 * but things are still usable. */
static void initializeTtys(void) {
    int fd, n;
    char dev[] = "/dev/ttyX";

    for (n = 9; n > 0; n--) {
	sprintf(dev, "/dev/tty%d", n);
	mknod(dev, 0600, S_IFCHR | makedev(4, n));
	fd = open(dev, O_RDWR|O_NOCTTY);
	if (fd >= 0) {
	    ioctl(fd, VT_ACTIVATE, n);
	    if (n == 1)
		ioctl(fd, VT_WAITACTIVE, n);
	    close(fd);
	} else
	    logMessage(ERROR, "failed to initialize %s", dev);
    }
}

static void spawnShell(void) {
    pid_t pid;

    if (FL_SERIAL(flags) || FL_NOSHELL(flags)) {
        logMessage(INFO, "not spawning a shell");
        return;
    } else if (access("/bin/sh",  X_OK))  {
        logMessage(ERROR, "cannot open shell - /bin/sh doesn't exist");
        return;
    }

    if (!(pid = fork())) {
	int fd;

    	fd = open("/dev/tty2", O_RDWR|O_NOCTTY);
    	if (fd < 0) {
            logMessage(ERROR, "cannot open /dev/tty2 -- no shell will be provided");
	    return;
	}

        dup2(fd, 0);
        dup2(fd, 1);
        dup2(fd, 2);
        
        close(fd);
        setsid();

	/* enable UTF-8 console */
	printf("\033%%G");
	fflush(stdout);
	isysLoadFont();
	
        if (ioctl(0, TIOCSCTTY, NULL)) {
            logMessage(ERROR, "could not set new controlling tty");
        }
        
        signal(SIGINT, SIG_DFL);
        signal(SIGTSTP, SIG_DFL);

        if (!access("/mnt/source/RHupdates/pyrc.py", R_OK|X_OK))
            setenv("PYTHONSTARTUP", "/mnt/source/RHupdates/pyrc.py", 1);
        else if (!access("/tmp/updates/pyrc.py", R_OK|X_OK))
            setenv("PYTHONSTARTUP", "/tmp/updates/pyrc.py", 1);
        else if (!access("/usr/lib/anaconda-runtime/pyrc.py", R_OK|X_OK))
            setenv("PYTHONSTARTUP", "/usr/lib/anaconda-runtime/pyrc.py", 1);
        setenv("LD_LIBRARY_PATH", LIBPATH, 1);
        setenv("LANG", "C", 1);
        
        if (execl("/bin/sh", "-/bin/sh", NULL) == -1) {
            logMessage(CRITICAL, "exec of /bin/sh failed: %s", strerror(errno));
            exit(1);
        }
    }

    return;
}

void loadUpdates(struct loaderData_s *loaderData) {
    int done = 0;
    int rc;
    char * device = NULL, ** devNames = NULL;
    char * buf;
    int num = 0;

    do { 
        rc = getRemovableDevices(&devNames);
        if (rc == 0) 
            return;

        /* we don't need to ask which to use if they only have one */
        if (rc == 1) {
            device = strdup(devNames[0]);
            free(devNames);
        } else {
            startNewt();
            rc = newtWinMenu(_("Update Disk Source"),
                             _("You have multiple devices which could serve "
                               "as sources for an update disk.  Which would "
                               "you like to use?"), 40, 10, 10,
                             rc < 6 ? rc : 6, devNames,
                             &num, _("OK"), _("Back"), NULL);
            
            if (rc == 2) {
                free(devNames);
                return;
            }
            loaderData->updatessrc = strdup(devNames[num]);
            free(devNames);
        }


        buf = sdupprintf(_("Insert your updates disk into /dev/%s and press "
                           "\"OK\" to continue."), loaderData->updatessrc);
        rc = newtWinChoice(_("Updates Disk"), _("OK"), _("Cancel"), buf);
        if (rc == 2)
            return;

        logMessage(INFO, "UPDATES device is %s", loaderData->updatessrc);

        devMakeInode(loaderData->updatessrc, "/tmp/upd.disk");
        if (doPwMount("/tmp/upd.disk", "/tmp/update-disk", "ext2", 
                      IMOUNT_RDONLY, NULL) &&
            doPwMount("/tmp/upd.disk", "/tmp/update-disk", "iso9660", 
                      IMOUNT_RDONLY, NULL)) {
            newtWinMessage(_("Error"), _("OK"), 
                           _("Failed to mount updates disk"));
        } else {
            /* Copy everything to /tmp/updates so we can unmount the disk  */
            winStatus(40, 3, _("Updates"), _("Reading anaconda updates..."));
            if (!copyDirectory("/tmp/update-disk", "/tmp/updates")) done = 1;
            newtPopWindow();
            umount("/tmp/update-disk");
        }
    } while (!done);

    return;
}

static int loadUpdatesFromRemote(char * url, struct loaderData_s * loaderData) {
    int rc = getFileFromUrl(url, "/tmp/updates.img", loaderData);

    if (rc != 0)
        return rc;

    copyUpdatesImg("/tmp/updates.img");
    unlink("/tmp/updates.img");
    return 0;
}

static void checkForHardDrives(void) {
    int i;
    struct device ** devices;

    devices = probeDevices(CLASS_HD, BUS_UNSPEC, PROBE_LOADED);
    if (devices)
        return;

    return;

    /* If they're using kickstart, assume they might know what they're doing.
     * Worst case is we fail later */
    if (FL_KICKSTART(flags)) {
        logMessage(WARNING, "no hard drives found, but in kickstart so continuing anyway");
        return;
    }
    
    startNewt();
    i = newtWinChoice(_("Warning"), _("Yes"), _("No"),
                      _("No hard drives have been found.  You probably need "
                        "to manually choose device drivers for the "
                        "installation to succeed.  Would you like to "
                        "select drivers now?"));
    if (i != 2)
        flags |= LOADER_FLAGS_ISA;

    return;
}

static void writeVNCPasswordFile(char *pfile, char *password) {
    FILE *f;

    f = fopen(pfile, "w+");
    fprintf(f, "%s\n", password);
    fclose(f);
}

/* read information from /tmp/netinfo (written by linuxrc) */
static void readNetInfo(struct loaderData_s ** ld) {
    int i;
    struct loaderData_s * loaderData = *ld;
    FILE *f;
    /* FIXME: arbitrary size that works, but could blow up in the future */
    int bufsiz = 100;
    char buf[bufsiz], *vname, *vparm;

    f = fopen("/tmp/netinfo", "r");
    if (!f)
        return;

    /* FIXME: static buffers lead to pain */
    vname = (char *)malloc(sizeof(char)*15);
    vparm = (char *)malloc(sizeof(char)*85);

    /* make sure everything is NULL before we begin copying info */
    loaderData->ip = NULL;
    loaderData->netmask = NULL;
    loaderData->gateway = NULL;
    loaderData->dns = NULL;
    loaderData->hostname = NULL;
    loaderData->peerid = NULL;
    loaderData->subchannels = NULL;
    loaderData->portname = NULL;
    loaderData->nettype = NULL;
    loaderData->ctcprot = NULL;
    loaderData->layer2 = NULL;
    loaderData->macaddr = NULL;
    loaderData->portno = NULL;

    /*
     * The /tmp/netinfo file is written out by /sbin/init on s390x (which is
     * really the linuxrc.s390 script).  It's a shell-sourcable file with
     * various system settings needing for the system instance.
     *
     * The goal of this function is to read in only the network settings
     * and populate the loaderData structure.
     */
    while(fgets(buf, bufsiz, f)) {
        /* trim whitespace from end */
        i = 0;
        while (!isspace(buf[i]) && i < (bufsiz-1))
            i++;
        buf[i] = '\0';

        /* break up var name and value */
        if (strstr(buf, "=")) {
            vname = strtok(buf, "=");
            if (vname == NULL)
                continue;

            vparm = strtok(NULL, "=");
            if (vparm == NULL)
                continue;

            if (!strncmp(vname, "IPADDR", 6)) {
                loaderData->ip = strdup(vparm);
            }

            if (!strncmp(vname, "NETMASK", 7))
                loaderData->netmask = strdup(vparm);

            if (!strncmp(vname, "GATEWAY", 7))
                loaderData->gateway = strdup(vparm);

            if (!strncmp(vname, "DNS", 3))
                loaderData->dns = strdup(vparm);

            if (!strncmp(vname, "MTU", 3))
                loaderData->mtu = atoi(vparm);

            if (!strncmp(vname, "PEERID", 6))
                loaderData->peerid = strdup(vparm);

            if (!strncmp(vname, "SUBCHANNELS", 12))
                loaderData->subchannels = strdup(vparm);

            if (!strncmp(vname, "PORTNAME", 8))
                loaderData->portname = strdup(vparm);

            if (!strncmp(vname, "NETTYPE", 7))
                loaderData->nettype = strdup(vparm);

            if (!strncmp(vname, "CTCPROT", 7))
                loaderData->ctcprot = strdup(vparm);

            if (!strncmp(vname, "LAYER2", 6))
                loaderData->layer2 = strdup(vparm);

            if (!strncmp(vname, "PORTNO", 6))
                loaderData->portno = strdup(vparm);

            if (!strncmp(vname, "MACADDR", 7))
                loaderData->macaddr = strdup(vparm);

            if (!strncmp(vname, "HOSTNAME", 8))
                loaderData->hostname = strdup(vparm);
        }
    }

    if (loaderData->ip && loaderData->netmask)
        flags |= LOADER_FLAGS_HAVE_CMSCONF;

    fclose(f);
}

/* parse anaconda or pxelinux-style ip= arguments
 * pxelinux format: ip=<client-ip>:<boot-server-ip>:<gw-ip>:<netmask>
 * anaconda format: ip=<client-ip> netmask=<netmask> gateway=<gw-ip>
*/
static void parseCmdLineIp(struct loaderData_s * loaderData, char *argv)
{
    /* Detect pxelinux */
    if (strstr(argv, ":") != NULL) {
        char *start, *end;

        /* IP */
        start = argv + 3;
        end = strstr(start, ":");
        loaderData->ip = strndup(start, end-start);
        loaderData->ipinfo_set = 0;

        /* Boot server */
        if (end + 1 == '\0')
            return;
        start = end + 1;
        end = strstr(start, ":");
        if (end == NULL)
            return;

        /* Gateway */
        if (end + 1 == '\0')
            return;
        start = end + 1;
        end = strstr(start, ":");
        if (end == NULL) {
            loaderData->gateway = strdup (start);
            return;
        } else {
            loaderData->gateway = strndup(start, end-start);
        }

        /* Netmask */
        if (end + 1 == '\0')
            return;
        start = end + 1;
        loaderData->netmask = strdup(start);
    } else {
        loaderData->ip = strdup(argv + 3);
        loaderData->ipinfo_set = 0;
    }

    flags |= LOADER_FLAGS_IP_PARAM;
}

/*
 * parse anaconda ipv6= arguments
 */
static void parseCmdLineIpv6(struct loaderData_s * loaderData, char *argv)
{
    /* right now we only accept ipv6= arguments equal to:
     *     dhcp     DHCPv6 call
     *     auto     RFC 2461 neighbor discovery
     */
    loaderData->ipv6 = NULL;

    if (!strncmp(str2lower(argv), "ipv6=dhcp", 9)) {
        loaderData->ipv6 = strdup("dhcp");
    } else if (!strncmp(str2lower(argv), "ipv6=auto", 9)) {
        loaderData->ipv6 = strdup("auto");
    }

    if (loaderData->ipv6 != NULL) {
        loaderData->ipv6info_set = 1;
        flags |= LOADER_FLAGS_IPV6_PARAM;
    }

    return;
}

/* parses /proc/cmdline for any arguments which are important to us.  
 * NOTE: in test mode, can specify a cmdline with --cmdline
 */
static void parseCmdLineFlags(struct loaderData_s * loaderData,
                              char * cmdLine) {
    int fd;
    char buf[1024];
    int len;
    char ** argv;
    int argc;
    int numExtraArgs = 0;
    int i;
    char *front;

    /* if we have any explicit cmdline (probably test mode), we don't want
     * to parse /proc/cmdline */
    if (!cmdLine) {
        if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return;
        len = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (len <= 0) return;
        
        buf[len] = '\0';
        cmdLine = buf;
    }
    
    if (poptParseArgvString(cmdLine, &argc, (const char ***) &argv))
        return;

    /* we want to default to graphical and allow override with 'text' */
    flags |= LOADER_FLAGS_GRAPHICAL;

    for (i=0; i < argc; i++) {
        if (!strcasecmp(argv[i], "expert")) {
            flags |= LOADER_FLAGS_EXPERT;
            logMessage(INFO, "expert got used, ignoring");
            /* flags |= (LOADER_FLAGS_EXPERT | LOADER_FLAGS_MODDISK | 
                        LOADER_FLAGS_ASKMETHOD);*/
        } else if (!strcasecmp(argv[i], "askmethod"))
            flags |= LOADER_FLAGS_ASKMETHOD;
        else if (!strcasecmp(argv[i], "asknetwork"))
            flags |= LOADER_FLAGS_ASKNETWORK;
        else if (!strcasecmp(argv[i], "noshell"))
            flags |= LOADER_FLAGS_NOSHELL;
        else if (!strcasecmp(argv[i], "mediacheck"))
            flags |= LOADER_FLAGS_MEDIACHECK;
        else if (!strcasecmp(argv[i], "nousbstorage"))
            flags |= LOADER_FLAGS_NOUSBSTORAGE;
        else if (!strcasecmp(argv[i], "nousb"))
            flags |= LOADER_FLAGS_NOUSB;
        else if (!strcasecmp(argv[i], "ub"))
            flags |= LOADER_FLAGS_UB;
        else if (!strcasecmp(argv[i], "telnet"))
            flags |= LOADER_FLAGS_TELNETD;
        else if (!strcasecmp(argv[i], "nofirewire"))
            flags |= LOADER_FLAGS_NOIEEE1394;
        else if (!strcasecmp(argv[i], "nonet"))
            flags |= LOADER_FLAGS_NONET;
        else if (!strcasecmp(argv[i], "nostorage"))
            flags |= LOADER_FLAGS_NOSTORAGE;
        else if (!strcasecmp(argv[i], "noprobe"))
            flags |= (LOADER_FLAGS_NONET | LOADER_FLAGS_NOSTORAGE | LOADER_FLAGS_NOUSB | LOADER_FLAGS_NOIEEE1394);
        else if (!strcasecmp(argv[i], "nopcmcia"))
            flags |= LOADER_FLAGS_NOPCMCIA;
        else if (!strcasecmp(argv[i], "text")) {
            flags |= LOADER_FLAGS_TEXT;
            flags &= ~LOADER_FLAGS_GRAPHICAL;
        }
        else if (!strcasecmp(argv[i], "graphical"))
            flags |= LOADER_FLAGS_GRAPHICAL;
        else if (!strcasecmp(argv[i], "cmdline"))
            flags |= LOADER_FLAGS_CMDLINE;
        else if (!strncasecmp(argv[i], "updates=", 8))
            loaderData->updatessrc = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "updates", 7))
            flags |= LOADER_FLAGS_UPDATES;
        else if (!strcasecmp(argv[i], "isa"))
            flags |= LOADER_FLAGS_ISA;
        else if (!strncasecmp(argv[i], "dd=", 3) || 
                 !strncasecmp(argv[i], "driverdisk=", 11)) {
            loaderData->ddsrc = strdup(argv[i] + 
                                       (argv[i][1] == 'r' ? 11 : 3));
        }
        else if (!strcasecmp(argv[i], "dd") || 
                 !strcasecmp(argv[i], "driverdisk"))
            flags |= LOADER_FLAGS_MODDISK;
        else if (!strcasecmp(argv[i], "dlabel=on"))
            flags |= LOADER_FLAGS_AUTOMODDISK;
        else if (!strcasecmp(argv[i], "dlabel=off"))
            flags &= ~LOADER_FLAGS_AUTOMODDISK;
        else if (!strcasecmp(argv[i], "rescue"))
            flags |= LOADER_FLAGS_RESCUE;
        else if (!strcasecmp(argv[i], "nopass"))
            flags |= LOADER_FLAGS_NOPASS;
        else if (!strcasecmp(argv[i], "serial")) 
            flags |= LOADER_FLAGS_SERIAL;
        else if (!strcasecmp(argv[i], "nofb"))
            flags |= LOADER_FLAGS_NOFB;
        else if (!strcasecmp(argv[i], "noipv4")) {
            flags |= LOADER_FLAGS_NOIPV4;
        } else if (!strcasecmp(argv[i], "noipv6")) {
            flags |= LOADER_FLAGS_NOIPV6;
        } else if (!strcasecmp(argv[i], "kssendmac")) {
            flags |= LOADER_FLAGS_KICKSTART_SEND_MAC;
        } else if (!strcasecmp(argv[i], "noeject")) {
            flags |= LOADER_FLAGS_NOEJECT;
        } else if (!strncasecmp(argv[i], "loglevel=", 9)) {
            if (!strcasecmp(argv[i]+9, "debug")) {
                loaderData->logLevel = strdup(argv[i]+9);
                setLogLevel(DEBUGLVL);
            }
            else if (!strcasecmp(argv[i]+9, "info")) {
                loaderData->logLevel = strdup(argv[i]+9);
                setLogLevel(INFO);
            }
            else if (!strcasecmp(argv[i]+9, "warning")) {
                loaderData->logLevel = strdup(argv[i]+9);
                setLogLevel(WARNING);
            }
            else if (!strcasecmp(argv[i]+9, "error")) {
                loaderData->logLevel = strdup(argv[i]+9);
                setLogLevel(ERROR);
            }
            else if (!strcasecmp(argv[i]+9, "critical")) {
                loaderData->logLevel = strdup(argv[i]+9);
                setLogLevel(CRITICAL);
            }
        }
        else if (!strncasecmp(argv[i], "ksdevice=", 9)) {
            loaderData->netDev = strdup(argv[i] + 9);

            /* Scan the MAC address and replace '-' with ':'.  This shouldn't
             * really be getting supplied, but it was accidentally supported
             * in RHEL4 and we need to continue support for now.
             */
            front = loaderData->netDev;
            if (front) {
                while (*front != '\0') {
                    if (*front == '-')
                        *front = ':';
                    front++;
                }
            }

            loaderData->netDev_set = 1;
        }
        else if (!strncmp(argv[i], "BOOTIF=", 7)) {
            /* +10 so that we skip over the leading 01- */
            loaderData->bootIf = strdup(argv[i] + 10);

            /* scan the BOOTIF value and replace '-' with ':' */
            front = loaderData->bootIf;
            if (front) {
                while (*front != '\0') {
                    if (*front == '-')
                        *front = ':';
                    front++;
                }
            }

            loaderData->bootIf_set = 1;
        } else if (!strncasecmp(argv[i], "dhcpclass=", 10)) {
            loaderData->netCls = strdup(argv[i] + 10);
            loaderData->netCls_set = 1;
        }
        else if (!strcasecmp(argv[i], "ks") || !strncasecmp(argv[i], "ks=", 3))
            loaderData->ksFile = strdup(argv[i]);
        else if (!strncasecmp(argv[i], "display=", 8))
            setenv("DISPLAY", argv[i] + 8, 1);
        else if ((!strncasecmp(argv[i], "lang=", 5)) && 
                 (strlen(argv[i]) > 5))  {
            loaderData->lang = strdup(argv[i] + 5);
            loaderData->lang_set = 1;
        }
        else if (!strncasecmp(argv[i], "keymap=", 7) &&
                   (strlen(argv[i]) > 7)) {
            loaderData->kbd = strdup(argv[i] + 7);
            loaderData->kbd_set = 1;
        }
        else if (!strncasecmp(argv[i], "method=", 7))
            setMethodFromCmdline(argv[i] + 7, loaderData);
        else if (!strncasecmp(argv[i], "ip=", 3))
            parseCmdLineIp(loaderData, argv[i]);
        else if (!strncasecmp(argv[i], "ipv6=", 5))
            parseCmdLineIpv6(loaderData, argv[i]);
        else if (!strncasecmp(argv[i], "netmask=", 8)) 
            loaderData->netmask = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "gateway=", 8))
            loaderData->gateway = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "dns=", 4))
            loaderData->dns = strdup(argv[i] + 4);
        else if (!strncasecmp(argv[i], "ethtool=", 8))
            loaderData->ethtool = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "essid=", 6))
            loaderData->essid = strdup(argv[i] + 6);
        else if (!strncasecmp(argv[i], "mtu=", 4))
            loaderData->mtu = atoi(argv[i] + 4);
        else if (!strncasecmp(argv[i], "wepkey=", 7))
            loaderData->wepkey = strdup(argv[i] + 7);
        else if (!strncasecmp(argv[i], "linksleep=", 10))
            num_link_checks = atoi(argv[i] + 10);
        else if (!strncasecmp(argv[i], "nicdelay=", 9))
            post_link_sleep = atoi(argv[i] + 9);
        else if (!strncasecmp(argv[i], "dhcptimeout=", 12))
            loaderData->dhcpTimeout = atoi(argv[i] + 12);
        else if (!strncasecmp(argv[i], "selinux=0", 9))
            flags &= ~LOADER_FLAGS_SELINUX;
        else if (!strncasecmp(argv[i], "selinux", 7))
            flags |= LOADER_FLAGS_SELINUX;
        else if (numExtraArgs < (MAX_EXTRA_ARGS - 1)) {
            /* go through and append args we just want to pass on to */
            /* the anaconda script, but don't want to represent as a */
            /* LOADER_FLAGS_XXX since loader doesn't care about these */
            /* particular options.                                   */
            /* do vncpassword case first */
            if (!strncasecmp(argv[i], "vncpassword=", 12)) {
                if (!FL_TESTING(flags))
                    writeVNCPasswordFile("/tmp/vncpassword.dat", argv[i]+12);
            }
            else if (!strncasecmp(argv[i], "resolution=", 11) ||
                     !strncasecmp(argv[i], "lowres", 6) ||
                     !strncasecmp(argv[i], "nomount", 7) ||
                     !strncasecmp(argv[i], "vnc", 3) ||
                     !strncasecmp(argv[i], "vncconnect=", 11) ||
                     !strncasecmp(argv[i], "headless", 8) ||
                     !strncasecmp(argv[i], "usefbx", 6) ||
                     !strncasecmp(argv[i], "mpath", 6) ||
                     !strncasecmp(argv[i], "nompath", 8) ||
                     !strncasecmp(argv[i], "dmraid", 6) ||
                     !strncasecmp(argv[i], "nodmraid", 8) ||
                     !strncasecmp(argv[i], "xdriver=", 8) ||
                     !strncasecmp(argv[i], "vesa", 4) ||
                     !strncasecmp(argv[i], "syslog=", 7)) { 

                /* vnc implies graphical */
                if (!strncasecmp(argv[i], "vnc", 3))
                    flags |= LOADER_FLAGS_GRAPHICAL;

                if (!strncasecmp(argv[i], "vesa", 4)) {
                    if (asprintf(&extraArgs[numExtraArgs],
                                 "--xdriver=vesa") == -1)
                        return;
                    logMessage(WARNING, "\"vesa\" command line argument is deprecated.  Use \"xdriver=vesa\".");
                } else {
                    if (asprintf(&extraArgs[numExtraArgs],"--%s",argv[i]) == -1)
                        return;
                }
                numExtraArgs += 1;

                if (numExtraArgs > (MAX_EXTRA_ARGS - 2)) {
                     logMessage(WARNING, "Too many command line arguments (max "
                                "allowed is %d), rest will be dropped.",
                                MAX_EXTRA_ARGS);
                }
            }
        }
    }

    readNetInfo(&loaderData);

    /* NULL terminates the array of extra args */
    extraArgs[numExtraArgs] = NULL;

    return;
}


#if 0
/* determine if we are using a framebuffer console.  return 1 if so */
static int checkFrameBuffer() {
    int fd;
    int rc = 0;
    struct fb_fix_screeninfo fix;

    if ((fd = open("/dev/fb0", O_RDONLY)) == -1) {
        return 0;
    }
    
    if (ioctl(fd, FBIOGET_FSCREENINFO, &fix) >= 0) {
        rc = 1;
    }
    close(fd);
    return rc;
}
#endif


/* make sure they have enough ram */
static void checkForRam(void) {
    if (totalMemory() < MIN_RAM) {
        char *buf;
        buf = sdupprintf(_("You do not have enough RAM to install %s "
                           "on this machine."), getProductName());
        startNewt();
        newtWinMessage(_("Error"), _("OK"), buf);
        free(buf);
        stopNewt();
        exit(0);
    }
}

static int haveDeviceOfType(int type, moduleList modLoaded) {
    struct device ** devices;

    devices = probeDevices(type, BUS_UNSPEC, PROBE_LOADED);
    if (devices) {
        return 1;
    }
    return 0;
}

/* fsm for the basics of the loader. */
static char *doLoaderMain(char * location,
                          struct loaderData_s * loaderData,
                          moduleInfoSet modInfo,
                          moduleList modLoaded,
                          moduleDeps * modDepsPtr) {
    enum { STEP_LANG, STEP_KBD, STEP_METHOD, STEP_DRIVER, 
           STEP_DRIVERDISK, STEP_NETWORK, STEP_IFACE,
           STEP_IP, STEP_URL, STEP_DONE } step;
    char * url = NULL;
    int dir = 1;
    int rc, i, query=0;

    char * installNames[10]; /* 10 install methods will be enough for anyone */
    int numValidMethods = 0;
    int validMethods[10];
    int methodNum = -1;

    int needed = -1;
    int needsNetwork = 0;

    int rhcdfnd = 0;

    char * devName = NULL;
    static struct networkDeviceConfig netDev;

    char * kbdtype = NULL;

    for (i = 0; i < numMethods; i++, numValidMethods++) {
        installNames[numValidMethods] = installMethods[i].name;
        validMethods[numValidMethods] = i;
    }
    installNames[numValidMethods] = NULL;

    /* have we preselected this to be our install method? */
    if (loaderData->method >= 0) {
        methodNum = loaderData->method;
        /* disable the fast path (#102652) */
        flags |= LOADER_FLAGS_ASKMETHOD;
    }

    /* check to see if we have a CD.  If we have one, then
     * we can fast-path the CD and not make people answer questions in 
     * text mode.  */
    if (!FL_ASKMETHOD(flags) && !FL_KICKSTART(flags)) {
        url = findAnacondaCD(location, modInfo, modLoaded, * modDepsPtr, !FL_RESCUE(flags));
        /* if we found a CD and we're not in rescue or vnc mode return */
        /* so we can short circuit straight to stage 2 from CD         */
        if (url && (!FL_RESCUE(flags) && !hasGraphicalOverride()
#if !defined(__s390__) && !defined(__s390x__)
                    && !ibft_present()
#endif
        ))
            return url;
        else {
            rhcdfnd = 1;
            methodNum = 0;
        }
    }

    if (!FL_CMDLINE(flags))
        startNewt();

    step = STEP_LANG;

    while (step != STEP_DONE) {
        switch(step) {
        case STEP_LANG:
            if (loaderData->lang && (loaderData->lang_set == 1)) {
                setLanguage(loaderData->lang);
            } else {
                chooseLanguage(&loaderData->lang);
            }
            step = STEP_KBD;
            dir = 1;
            break;
        case STEP_KBD:
            if (loaderData->kbd && (loaderData->kbd_set == 1)) {
                /* JKFIXME: this is broken -- we should tell of the 
                 * failure; best by pulling code out in kbd.c to use */
                if (isysLoadKeymap(loaderData->kbd)) {
                    logMessage(WARNING, "requested keymap %s is not valid, asking", loaderData->kbd);
                    loaderData->kbd = NULL;
                    loaderData->kbd_set = 0;
                    break;
                }
                rc = LOADER_NOOP;
            } else {
                /* JKFIXME: should handle kbdtype, too probably... but it 
                 * just matters for sparc */
                if (!FL_CMDLINE(flags))
                    rc = chooseKeyboard(loaderData, &kbdtype);
                else
                   rc = LOADER_NOOP;
            }
            if (rc == LOADER_NOOP) {
                if (dir == -1)
                    step = STEP_LANG;
                else
                    step = STEP_METHOD;
                break;
            }

            if (rc == LOADER_BACK) {
                step = STEP_LANG;
                dir = -1;
            } else {
                step = STEP_METHOD;
                dir = 1;
            }

            break;

        case STEP_METHOD:
            /* this is kind of crappy, but we want the first few questions
             * to be asked when using rescue mode even if we're going
             * to short-circuit to the CD.
             *
             * Alternately, if we're in a VNC install based from CD we
             * can skip this step because we already found the CD */
            if (url) {
                if (FL_RESCUE(flags)) {
                    return url;
                } else if (rhcdfnd) {
                    step = STEP_NETWORK;
                    dir = 1;
                    break;
                }
            }	    

            needed = -1;

            if (loaderData->method != -1 && methodNum != -1) {
                /* dont forget the dir var. */
                if ( dir == 1 ){
                    rc = 1;
                }else{
                    rc = -1;
                }
            } else {
                /* we need to set these each time through so that we get
                 * updated for language changes (#83672) */
                for (i = 0; i < numMethods; i++) {
                    installNames[i] = _(installMethods[i].name);
                }
                installNames[i] = NULL;

                rc = newtWinMenu(FL_RESCUE(flags) ? _("Rescue Method") :
                                 _("Installation Method"),
                                 FL_RESCUE(flags) ?
                                 _("What type of media contains the rescue "
                                   "image?") :
                                 _("What type of media contains the packages to "
                                   "be installed?"),
                                 30, 10, 20, 6, installNames, &methodNum, 
                                 _("OK"), _("Back"), NULL);
            } 

            if (rc && rc != 1) {
                step = STEP_KBD;
                dir = -1;
            } else {
                needed = installMethods[validMethods[methodNum]].deviceType;
                step = STEP_DRIVER;
                dir = 1;
            }
            break;

        case STEP_DRIVER: {
            if (needed == -1 || haveDeviceOfType(needed, modLoaded)) {
                step = STEP_NETWORK;
                dir = 1;
                needed = -1;
                break;
            }


            rc = newtWinTernary(_("No driver found"), _("Select driver"),
                                _("Use a driver disk"), _("Back"),
                                _("Unable to find any devices of the type "
                                  "needed for this installation type.  "
                                  "Would you like to manually select your "
                                  "driver or use a driver disk?"));
            if (rc == 2) {
                step = STEP_DRIVERDISK;
                dir = 1;
                break;
            } else if (rc == 3) {
                step = STEP_METHOD;
                dir = -1;
                break;
            }
            
            chooseManualDriver(installMethods[validMethods[methodNum]].deviceType,
                               loaderData);
            /* it doesn't really matter what we return here; we just want
             * to reprobe and make sure we have the driver */
            step = STEP_DRIVER;
            break;
        }

        case STEP_DRIVERDISK:

            rc = loadDriverFromMedia(needed, loaderData, 0, 0);
            if (rc == LOADER_BACK) {
                step = STEP_DRIVER;
                dir = -1;
                break;
            }

            /* need to come back to driver so that we can ensure that we found
             * the right kind of driver after loading the driver disk */
            step = STEP_DRIVER;
            break;

        case STEP_NETWORK:
            if ( (installMethods[validMethods[methodNum]].deviceType != 
                  CLASS_NETWORK) && (!hasGraphicalOverride()) &&
                 !FL_ASKNETWORK(flags)
#if !defined(__s390__) && !defined(__s390x__)
                 && !ibft_present()
#endif
               ) {
                needsNetwork = 0;
                if (dir == 1) 
                    step = STEP_URL;
                else if (dir == -1)
                    step = STEP_METHOD;
                break;
            }

            needsNetwork = 1;
            if (!haveDeviceOfType(CLASS_NETWORK, modLoaded)) {
                needed = CLASS_NETWORK;
                step = STEP_DRIVER;
                break;
            }
            logMessage(INFO, "need to set up networking");

            initLoopback();
            memset(&netDev, 0, sizeof(netDev));
            netDev.isDynamic = 1;

            /* fall through to interface selection */
        case STEP_IFACE:
            logMessage(INFO, "going to pick interface");

            /* skip configureTCPIP() screen for kickstart (#260621) */
            if (loaderData->ksFile)
                flags |= LOADER_FLAGS_IS_KICKSTART;

            if (FL_HAVE_CMSCONF(flags)) {
                loaderData->ipinfo_set = 1;
                loaderData->ipv6info_set = 1;
            } else {
                loaderData->ipinfo_set = 0;
                loaderData->ipv6info_set = 0;
            }

            rc = chooseNetworkInterface(loaderData);
            if ((rc == LOADER_BACK) || (rc == LOADER_ERROR) ||
                ((dir == -1) && (rc == LOADER_NOOP))) {
                step = STEP_METHOD;
                dir = -1;
                break;
            }
            else
               dir = 1;

            devName = loaderData->netDev;
            strcpy(netDev.dev.device, devName);

            /* fall through to ip config */
        case STEP_IP: {
            if (loaderData->ip != NULL) {
                query = !strncmp(loaderData->ip, "query", 5);
            }

            if (!needsNetwork) {
                step = STEP_METHOD; /* only hit going back */
                break;
            }

            logMessage(INFO, "going to do getNetConfig");

            if (query || FL_NOIPV4(flags) || (!FL_IP_PARAM(flags) && !FL_KICKSTART(flags)))
                loaderData->ipinfo_set = 0;
            else
                loaderData->ipinfo_set = 1;

            if (query || FL_NOIPV6(flags) || (!FL_IPV6_PARAM(flags) && !FL_KICKSTART(flags)))
                loaderData->ipv6info_set = 0;
            else
                loaderData->ipv6info_set = 1;

            /* s390 provides all config info by way of the CMS conf file */
            if (FL_HAVE_CMSCONF(flags)) {
                loaderData->ipinfo_set = 1;
                loaderData->ipv6info_set = 1;
            }

            /* populate netDev based on any kickstart data */
            if (loaderData->ipinfo_set) {
                netDev.preset = 1;
            }
            setupNetworkDeviceConfig(&netDev, loaderData);

            rc = readNetConfig(devName, &netDev, loaderData->netCls, methodNum, query);
            if ((rc == LOADER_NOOP) && (netDev.preset == 0)) {
                loaderData->ipinfo_set = 0;
                loaderData->ipv6info_set = 0;
            }

            if ((rc == LOADER_BACK) || (rc == LOADER_ERROR) ||
                ((dir == -1) && (rc == LOADER_NOOP))) {
                step = STEP_IFACE;
                dir = -1;
                break;
            }

            writeNetInfo("/tmp/netinfo", &netDev);
            step = STEP_URL;
            dir = 1;
        }

        case STEP_URL:
            logMessage(INFO, "starting to STEP_URL");
            /* if we found a CD already short circuit out */
            /* we get this case when we're doing a VNC install from CD */
            /* and we didnt short circuit earlier because we had to */
            /* prompt for network info for vnc to work */
            if (url && rhcdfnd)
                return url;

            url = installMethods[validMethods[methodNum]].mountImage(
                                      installMethods + validMethods[methodNum],
                                      location, loaderData, modInfo, modLoaded, 
                                      modDepsPtr);
            if (!url) {
                step = STEP_IP ;
                dir = -1;
            } else {
                logMessage(INFO, "got url %s", url);
                step = STEP_DONE;
                dir = 1;
            }
            break;
        default:
            break;
        }
    }

    return url;
}

static int manualDeviceCheck(struct loaderData_s *loaderData) {
    char ** devices;
    int i, j, rc, num = 0;
    struct moduleInfo * mi;
    unsigned int width = 40;
    char * buf;

    moduleInfoSet modInfo = loaderData->modInfo;
    moduleList modLoaded = loaderData->modLoaded;

    do {
        devices = malloc((modLoaded->numModules + 1) * sizeof(*devices));
        for (i = 0, j = 0; i < modLoaded->numModules; i++) {
            if (!modLoaded->mods[i].weLoaded) continue;
            
            if (!(mi = findModuleInfo(modInfo, modLoaded->mods[i].name)) ||
                (!mi->description))
                continue;

            devices[j] = sdupprintf("%s (%s)", mi->description, 
                                    modLoaded->mods[i].name);
            if (strlen(devices[j]) > width)
                width = strlen(devices[j]);
            j++;
        }

        devices[j] = NULL;

        if (width > 70)
            width = 70;

        if (j > 0) {
            buf = _("The following devices have been found on your system.");
        } else {
            buf = _("No device drivers have been loaded for your system.  "
                    "Would you like to load any now?");
        }

        rc = newtWinMenu(_("Devices"), buf, width, 10, 20, 
                         (j > 6) ? 6 : j, devices, &num, _("Done"), 
                         _("Add Device"), NULL);

        /* no leaky */
        for (i = 0; i < j; i++) 
            free(devices[j]);
        free(devices);

        if (rc != 2)
            break;

        chooseManualDriver(CLASS_UNSPEC, loaderData);
    } while (1);
    return 0;
}

/* JKFIXME: I don't really like this, but at least it isolates the ifdefs */
/* Either move dirname to %s_old or unlink depending on arch (unlink on all
 * !s390{,x} arches).  symlink to /mnt/runtime/dirname.  dirname *MUST* start
 * with a '/' */
static void migrate_runtime_directory(char * dirname) {
    char * runtimedir;
    int ret;

    runtimedir = sdupprintf("/mnt/runtime%s", dirname);
    if (!access(runtimedir, X_OK)) {
#if !defined(__s390__) && !defined(__s390x__)
        unlink(dirname);
#else
        char * olddir;

        olddir = sdupprintf("%s_old", dirname);
        rename(dirname, olddir);
        free(olddir);
#endif
        ret = symlink(runtimedir, dirname);
    }
    free(runtimedir);
}


static int hasGraphicalOverride() {
    int i;

    if (getenv("DISPLAY"))
        return 1;

    for (i = 0; extraArgs[i] != NULL; i++) {
        if (!strncasecmp(extraArgs[i], "--vnc", 5))
            return 1;
    }
    return 0;
}

void loaderSegvHandler(int signum) {
    void *array[10];
    size_t size;
    char **strings;
    size_t i, j;
    const char const * const errmsg = "loader received SIGSEGV!  Backtrace:\n";

    signal(signum, SIG_DFL); /* back to default */

    newtFinished();
    size = backtrace (array, 10);
    strings = backtrace_symbols (array, size);

    j = write(STDERR_FILENO, errmsg, strlen(errmsg));
    for (i = 0; i < size; i++) {
        j = write(STDERR_FILENO, strings[i], strlen(strings[i]));
        j = write(STDERR_FILENO, "\n", 1);
    }

    free (strings);
    exit(1);
}

void loaderUsrXHandler(int signum) {
    logMessage(INFO, "Sending signal %d to process %d\n", signum, init_pid);
    kill(init_pid, signum);
}

static int anaconda_trace_init(void) {
#if 0
    int fd;
#endif

#ifdef USE_MTRACE
    setenv("MALLOC_TRACE","/malloc",1);
    mtrace();
#endif
    /* We have to do this before we init bogl(), which doLoaderMain will do
     * when setting fonts for different languages.  It's also best if this
     * is well before we might take a SEGV, so they'll go to tty8 */
    initializeTtys();

#if 0
    fd = open("/dev/tty8", O_RDWR);
    close(STDERR_FILENO);
    dup2(fd, STDERR_FILENO);
    close(fd);
#endif

    /* set up signal handler */
    signal(SIGSEGV, loaderSegvHandler);
    signal(SIGABRT, loaderSegvHandler);

    return 0;
}

int main(int argc, char ** argv) {
    /* Very first thing, set up tracebacks and debug features. */
    int rc;

    struct stat sb;
    struct serial_struct si;
    int i;
    char * arg;
    FILE *f;

    char twelve = 12;

    moduleInfoSet modInfo;
    moduleList modLoaded;
    moduleDeps modDeps;

    char *url = NULL;

    char ** argptr, ** tmparg;
    char * anacondaArgs[50];
    int useRHupdates = 0;

    struct loaderData_s loaderData;

    char * cmdLine = NULL;
    char * ksFile = NULL;
    int testing = 0;
    int mediacheck = 0;
    char * virtpcon = NULL;
    
    struct ddlist *dd, *dditer;

    poptContext optCon;

    struct poptOption optionTable[] = {
        { "cmdline", '\0', POPT_ARG_STRING, &cmdLine, 0, NULL, NULL },
        { "ksfile", '\0', POPT_ARG_STRING, &ksFile, 0, NULL, NULL },
        { "test", '\0', POPT_ARG_NONE, &testing, 0, NULL, NULL },
        { "mediacheck", '\0', POPT_ARG_NONE, &mediacheck, 0, NULL, NULL},
        { "virtpconsole", '\0', POPT_ARG_STRING, &virtpcon, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    /* get init PID if we have it */
    if ((f = fopen("/var/run/init.pid", "r")) != NULL) {
        char linebuf[256];

        while (fgets(linebuf, sizeof(linebuf), f) != NULL) {
            errno = 0;
            init_pid = strtol(linebuf, NULL, 10);
            if (errno == EINVAL || errno == ERANGE) {
                logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
                init_pid = 1;
            }
        }

        fclose(f);
    }

    signal(SIGUSR1, loaderUsrXHandler);
    signal(SIGUSR2, loaderUsrXHandler);

    /* Make sure sort order is right. */
    setenv ("LC_COLLATE", "C", 1);	

    if (!strcmp(argv[0] + strlen(argv[0]) - 6, "insmod"))
        return ourInsmodCommand(argc, argv);
    if (!strcmp(argv[0] + strlen(argv[0]) - 8, "modprobe"))
        return ourInsmodCommand(argc, argv);
    if (!strcmp(argv[0] + strlen(argv[0]) - 5, "rmmod"))
        return ourRmmodCommand(argc, argv);

    rc = anaconda_trace_init();

    /* now we parse command line options */
    optCon = poptGetContext(NULL, argc, (const char **) argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
        fprintf(stderr, "bad option %s: %s\n",
                poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                poptStrerror(rc));
        exit(1);
    }

    if ((arg = (char *) poptGetArg(optCon))) {
        fprintf(stderr, "unexpected argument: %s\n", arg);
        exit(1);
    }

    if (!testing && !access("/var/run/loader.run", R_OK)) {
        printf(_("loader has already been run.  Starting shell.\n"));
        execl("/bin/sh", "-/bin/sh", NULL);
        exit(0);
    }
    
    f = fopen("/var/run/loader.run", "w+");
    fprintf(f, "%d\n", getpid());
    fclose(f);

    /* The fstat checks disallows serial console if we're running through
       a pty. This is handy for Japanese. */
    fstat(0, &sb);
    if (major(sb.st_rdev) != 3 && major(sb.st_rdev) != 136 && 
        (virtpcon == NULL)){
        if ((ioctl (0, TIOCLINUX, &twelve) < 0) && 
            (ioctl(0, TIOCGSERIAL, &si) != -1))
            flags |= LOADER_FLAGS_SERIAL;
    }

    if (testing) flags |= LOADER_FLAGS_TESTING;
    if (mediacheck) flags |= LOADER_FLAGS_MEDIACHECK;
    if (ksFile) flags |= LOADER_FLAGS_KICKSTART;
    if (virtpcon) flags |= LOADER_FLAGS_VIRTPCONSOLE;

    /* uncomment to send mac address in ks=http:/ header by default*/
    flags |= LOADER_FLAGS_KICKSTART_SEND_MAC;

    /* JKFIXME: I do NOT like this... it also looks kind of bogus */
#if defined(__s390__) && !defined(__s390x__)
    flags |= LOADER_FLAGS_NOSHELL | LOADER_FLAGS_NOUSB;
#endif

    /* XXX if RHEL, enable the AUTODD feature by default,
     * but we should come with more general way how to control this */
    if(!strncmp(getProductName(), "Red Hat", 7)){
      flags |= LOADER_FLAGS_AUTOMODDISK;
    }

    openLog(FL_TESTING(flags));
    if (!FL_TESTING(flags))
        openlog("loader", 0, LOG_LOCAL0);

    memset(&loaderData, 0, sizeof(loaderData));
    loaderData.method = -1;
    loaderData.fw_loader_pid = -1;
    loaderData.fw_search_pathz_len = -1;
    loaderData.dhcpTimeout = -1;

    extraArgs[0] = NULL;
    parseCmdLineFlags(&loaderData, cmdLine);

    if ((FL_SERIAL(flags) || FL_VIRTPCONSOLE(flags)) && 
        !hasGraphicalOverride())
        flags |= LOADER_FLAGS_TEXT;
    if (FL_SERIAL(flags))
        flags |= LOADER_FLAGS_NOFB;

    setupRamfs();

    set_fw_search_path(&loaderData, "/firmware:/lib/firmware:/usr/lib/firmware");
    start_fw_loader(&loaderData);

    arg = FL_TESTING(flags) ? "./module-info" : "/modules/module-info";
    modInfo = newModuleInfoSet();
    if (readModuleInfo(arg, modInfo, NULL, 0)) {
        fprintf(stderr, "failed to read %s\n", arg);
        sleep(5);
        stop_fw_loader(&loaderData);
        exit(1);
    }
    mlReadLoadedList(&modLoaded);
    modDeps = mlNewDeps();
    mlLoadDeps(&modDeps, "/modules/modules.dep");

    initializeConsole(modLoaded, modDeps, modInfo);

    checkForRam();

    /* iSeries vio console users will be telnetting in to the primary
       partition, so use a terminal type that is appripriate */
    if (isVioConsole())
        setenv("TERM", "vt100", 1);

#if defined(__powerpc__)  /* hack for pcspkr breaking ppc right now */
    mlLoadModuleSet("cramfs:vfat:nfs:loop:isofs:floppy:edd:squashfs", 
                    modLoaded, modDeps, modInfo);
#else
    mlLoadModuleSet("cramfs:vfat:nfs:loop:isofs:floppy:edd:pcspkr:squashfs", 
                    modLoaded, modDeps, modInfo);
#endif

    /* IPv6 support is conditional */
    ipv6Setup(modLoaded, modDeps, modInfo);

    /* now let's do some initial hardware-type setup */
    ideSetup(modLoaded, modDeps, modInfo);
    scsiSetup(modLoaded, modDeps, modInfo);
    dasdSetup(modLoaded, modDeps, modInfo);
    spufsSetup(modLoaded, modDeps, modInfo);

    /* Note we *always* do this. If you could avoid this you could get
       a system w/o USB keyboard support, which would be bad. */
    usbInitialize(modLoaded, modDeps, modInfo);
    
    /* now let's initialize any possible firewire.  fun */
    firewireInitialize(modLoaded, modDeps, modInfo);

    /* explicitly read this to let libkudzu know we want to merge
     * in future tables rather than replace the initial one */
    pciReadDrivers("/modules/modules.alias");
    
    if (loaderData.lang && (loaderData.lang_set == 1)) {
        setLanguage(loaderData.lang);
    }

    /* FIXME: this is a bit of a hack */
    loaderData.modLoaded = modLoaded;
    loaderData.modDepsPtr = &modDeps;
    loaderData.modInfo = modInfo;


    if (!canProbeDevices() || FL_MODDISK(flags)) {
        startNewt();
        
        loadDriverDisks(CLASS_UNSPEC, &loaderData);
    }

    if (!access("/dd.img", R_OK)) {
        logMessage(INFO, "found /dd.img, loading drivers");
        getDDFromSource(&loaderData, "path:/dd.img");
    }
    
    /* The detection requires at least the basic device nodes to be present... */
    createPartitionNodes();

    if(FL_AUTOMODDISK(flags)){
      mkdirChain("/etc/blkid");
      logMessage(INFO, "Trying to detect vendor driver discs");
      dd = findDriverDiskByLabel();
      dditer = dd;

      if (dd && !loaderData.ksFile) {
          startNewt();
      }

      while(dditer){
          /* If in interactive mode, ask for confirmation before loading the DD */
          if (!loaderData.ksFile) {
              char *buf = NULL;
              if (asprintf(&buf,
                          _("Driver disc was detected in %s. "
                            "Do you want to use it?."),
                           dditer->device) == -1) {
                  logMessage(ERROR, "asprintf error in Driver Disc code");
                  break;
              };

              rc = newtWinChoice(_("Driver disc detected"), _("Use it"), _("Skip it"),
                                 buf);
              free(buf);
              if (rc == 2) {
                  logMessage(INFO, "Skipping driver disk %s.", (char*)(dditer->device));
                  
                  /* next DD */
                  dditer = dditer->next;
                  continue;
              }
          }


	if(loadDriverDiskFromPartition(&loaderData, dditer->device)){
	  logMessage(ERROR, "Automatic driver disk loader failed for %s.", dditer->device);
	}
	else{
	  logMessage(INFO, "Automatic driver disk loader succeeded for %s.", dditer->device);
	}

        /* Next DD */
	dditer = dditer->next;
      }

      if (dd && !loaderData.ksFile) {
          stopNewt();
      }

      ddlist_free(dd);
    }
    
    /* this allows us to do an early load of modules specified on the
     * command line to allow automating the load order of modules so that
     * eg, certain scsi controllers are definitely first.
     * FIXME: this syntax is likely to change in a future release
     *        but is done as a quick hack for the present.
     */
    earlyModuleLoad(modInfo, modLoaded, modDeps, 0);
    if (loaderData.ddsrc != NULL) {
	/* If we load DUD over network (from ftp, http, or nfs location)
         * do not load storage drivers so that they can be updated
	 * from DUD before loading (#454478).
	 */
        if (!strncmp(loaderData.ddsrc, "nfs:", 4) || 
            !strncmp(loaderData.ddsrc, "ftp://", 6) ||
            !strncmp(loaderData.ddsrc, "http://", 7)) {
            uint64_t save_flags = flags;
            flags |= LOADER_FLAGS_NOSTORAGE;
            busProbe(modInfo, modLoaded, modDeps, 0);
            flags = save_flags;
        } else {
            busProbe(modInfo, modLoaded, modDeps, 0);
        }
        getDDFromSource(&loaderData, loaderData.ddsrc);
    } else {
        busProbe(modInfo, modLoaded, modDeps, 0);
    }

    /*
     * BUG#514971: If the mlx4_core is loaded load the mlx4_en too, since we do not use the modprobe rules
     */
    if(mlModuleInList("mlx4_core", modLoaded)){
        logMessage(INFO, "mlx4_core module detected, trying to load the Ethernet part of it (mlx4_en)");
        mlLoadModuleSet("mlx4_en", modLoaded, modDeps, modInfo);
    }

    /* JKFIXME: loaderData->ksFile is set to the arg from the command line,
     * and then getKickstartFile() changes it and sets FL_KICKSTART.  
     * kind of weird. */
    if (loaderData.ksFile || ksFile) {
        logMessage(INFO, "getting kickstart file");

        if (!ksFile)
            getKickstartFile(&loaderData);
        if (FL_KICKSTART(flags) && 
            (ksReadCommands((ksFile)?ksFile:loaderData.ksFile)!=LOADER_ERROR)) {
            runKickstart(&loaderData);
        }
    }

    if (FL_TELNETD(flags))
        startTelnetd(&loaderData, modInfo, modLoaded, modDeps);

    url = doLoaderMain("/mnt/source", &loaderData, modInfo, modLoaded, &modDeps);

    if (!FL_TESTING(flags)) {
        /* unlink dirs and link to the ones in /mnt/runtime */
        migrate_runtime_directory("/usr");
        migrate_runtime_directory("/lib");
        migrate_runtime_directory("/lib64");
    }

    /* now load SELinux policy before exec'ing anaconda and the shell
     * (if we're using SELinux) */
    if (FL_SELINUX(flags)) {
        if (mount("/selinux", "/selinux", "selinuxfs", 0, NULL)) {
            logMessage(ERROR, "failed to mount /selinux: %s, disabling SELinux", strerror(errno));
            flags &= ~LOADER_FLAGS_SELINUX;
        } else {
            /* FIXME: this is a bad hack for libselinux assuming things
             * about paths */
	    int ret;
            ret = symlink("/mnt/runtime/etc/selinux", "/etc/selinux");
            if (loadpolicy() == 0) {
                setexeccon(ANACONDA_CONTEXT);
            } else {
                logMessage(ERROR, "failed to load policy, disabling SELinux");
                flags &= ~LOADER_FLAGS_SELINUX;
            }
        }
    }

    logMessage(INFO, "getting ready to spawn shell now");
    
    spawnShell();  /* we can attach gdb now :-) */

    /* JKFIXME: kickstart devices crap... probably kind of bogus now though */


    /* we might have already loaded these, but trying again doesn't hurt */
    ideSetup(modLoaded, modDeps, modInfo);
    scsiSetup(modLoaded, modDeps, modInfo);
    busProbe(modInfo, modLoaded, modDeps, 0);

    checkForHardDrives();

    if ((!canProbeDevices() || FL_ISA(flags) || FL_NOPROBE(flags))
        && !loaderData.ksFile) {
        startNewt();
        manualDeviceCheck(&loaderData);
    }

    if (loaderData.updatessrc)
        loadUpdatesFromRemote(loaderData.updatessrc, &loaderData);
    else if (FL_UPDATES(flags))
        loadUpdates(&loaderData);

    mlLoadModuleSet("md:raid0:raid1:raid10:raid5:raid6:raid456:dm-raid45:fat:msdos:jbd2:crc16:ext4:jbd:ext3:lock_nolock:gfs2:reiserfs:jfs:xfs:dm-mod:dm-zero:dm-mirror:dm-snapshot:dm-multipath:dm-round-robin:dm-emc:dm-crypt:dm-mem-cache:dm-region_hash:dm-message:aes_generic:sha256", modLoaded, modDeps, modInfo);

    usbInitializeMouse(modLoaded, modDeps, modInfo);

    /* we've loaded all the modules we're going to.  write out a file
     * describing which scsi disks go with which scsi adapters */
    writeScsiDisks(modLoaded);

    /* if we are in rescue mode lets load st.ko for tape support */
    if (FL_RESCUE(flags))
        scsiTapeInitialize(modLoaded, modDeps, modInfo);

    /* we only want to use RHupdates on nfs installs.  otherwise, we'll 
     * use files on the first iso image and not be able to umount it */
    if (!strncmp(url, "nfs:", 4)) {
        logMessage(INFO, "NFS install method detected, will use RHupdates/");
        useRHupdates = 1;
    } else {
        useRHupdates = 0;
    }

    if (useRHupdates) {
        setenv("PYTHONPATH", "/tmp/updates:/tmp/product:/mnt/source/RHupdates", 1);
        setenv("LD_LIBRARY_PATH", 
               sdupprintf("/tmp/updates:/tmp/product:/mnt/source/RHupdates:%s",
                           LIBPATH), 1);
        add_fw_search_dir(&loaderData, "/tmp/updates/firmware");
        add_fw_search_dir(&loaderData, "/tmp/product/firmware");
        add_fw_search_dir(&loaderData, "/mnt/source/RHupdates/firmware");
        stop_fw_loader(&loaderData);
        start_fw_loader(&loaderData);
    } else {
        setenv("PYTHONPATH", "/tmp/updates:/tmp/product", 1);
        setenv("LD_LIBRARY_PATH", 
               sdupprintf("/tmp/updates:/tmp/product:%s", LIBPATH), 1);
        add_fw_search_dir(&loaderData, "/tmp/updates/firmware");
        add_fw_search_dir(&loaderData, "/tmp/product/firmware");
        stop_fw_loader(&loaderData);
        start_fw_loader(&loaderData);
    }

    if (!access("/mnt/runtime/usr/lib/libunicode-lite.so.1", R_OK))
        setenv("LD_PRELOAD", "/mnt/runtime/usr/lib/libunicode-lite.so.1", 1);
    if (!access("/mnt/runtime/usr/lib64/libunicode-lite.so.1", R_OK))
        setenv("LD_PRELOAD", "/mnt/runtime/usr/lib64/libunicode-lite.so.1", 1);

    argptr = anacondaArgs;

    if (!access("/tmp/updates/anaconda", X_OK))
        *argptr++ = "/tmp/updates/anaconda";
    else if (useRHupdates && !access("/mnt/source/RHupdates/anaconda", X_OK))
        *argptr++ = "/mnt/source/RHupdates/anaconda";
    else
        *argptr++ = "/usr/bin/anaconda";

    /* make sure /tmp/updates exists so that magic in anaconda to */
    /* symlink rhpl/ will work                                    */
    if (access("/tmp/updates", F_OK))
        mkdirChain("/tmp/updates");

    logMessage(INFO, "Running anaconda script %s", *(argptr-1));
    
    *argptr++ = "-m";
    if (strncmp(url, "ftp:", 4)) {
        *argptr++ = url;
    } else {
        int fd, ret;

        fd = open("/tmp/method", O_CREAT | O_TRUNC | O_RDWR, 0600);
        ret = write(fd, url, strlen(url));
        ret = write(fd, "\r", 1);
        close(fd);
        *argptr++ = "@/tmp/method";
    }

    /* add extra args - this potentially munges extraArgs */
    tmparg = extraArgs;
    while (*tmparg) {
        char *idx;
        
        logMessage(DEBUGLVL, "adding extraArg %s", *tmparg);
        idx = strchr(*tmparg, '=');
        if (idx &&  ((idx-*tmparg) < strlen(*tmparg))) {
            *idx = '\0';
            *argptr++ = *tmparg;
            *argptr++ = idx+1;
        } else {
            *argptr++ = *tmparg;
        }

        tmparg++;
    }

    if (FL_AUTOMODDISK(flags))
        *argptr++ = "--dlabel";

    if (FL_NOIPV4(flags))
        *argptr++ = "--noipv4";

    if (FL_NOIPV6(flags))
        *argptr++ = "--noipv6";

    if (FL_NOEJECT(flags))
        *argptr++ = "--noeject";

    if (FL_RESCUE(flags)) {
        *argptr++ = "--rescue";
        if (FL_SERIAL(flags))
            *argptr++ = "--serial";
    } else {
        if (FL_SERIAL(flags))
            *argptr++ = "--serial";
        if (FL_TEXT(flags))
            *argptr++ = "-T";
        else if (FL_GRAPHICAL(flags))
            *argptr++ = "--graphical";
        if (FL_CMDLINE(flags))
            *argptr++ = "-C";
        if (FL_EXPERT(flags))
            *argptr++ = "--expert";
        if (!FL_SELINUX(flags))
            *argptr++ = "--noselinux";
        else if (FL_SELINUX(flags))
            *argptr++ = "--selinux";
        
        if (FL_KICKSTART(flags)) {
            *argptr++ = "--kickstart";
            *argptr++ = loaderData.ksFile;
        }

        if (FL_VIRTPCONSOLE(flags)) {
            *argptr++ = "--virtpconsole";
            *argptr++ = virtpcon;
        }

        if (loaderData.updatessrc && FL_UPDATES(flags)) {
            *argptr++ = "--updates";
            *argptr++ = loaderData.updatessrc;
        }

        if ((loaderData.lang) && !FL_NOPASS(flags)) {
            *argptr++ = "--lang";
            *argptr++ = loaderData.lang;
        }
        
        if ((loaderData.kbd) && !FL_NOPASS(flags)) {
            *argptr++ = "--keymap";
            *argptr++ = loaderData.kbd;
        }

        if (loaderData.logLevel) {
            *argptr++ = "--loglevel";
            *argptr++ = loaderData.logLevel;
        }
        
        for (i = 0; i < modLoaded->numModules; i++) {
            if (!modLoaded->mods[i].path) continue;
            if (!strcmp(modLoaded->mods[i].path, 
                        "/mnt/runtime/modules/modules.cgz")) {
                continue;
            }
            
            *argptr++ = "--module";
            *argptr = alloca(80);
            sprintf(*argptr, "%s:%s", modLoaded->mods[i].path,
                    modLoaded->mods[i].name);
            
            argptr++;
        }
    }
    
    *argptr = NULL;
    
    stopNewt();
    closeLog();
    
    if (!FL_TESTING(flags)) {
        int pid, status, rc;
        char * buf;

        if (FL_RESCUE(flags))
            buf = sdupprintf(_("Running anaconda, the %s rescue mode - please wait...\n"), getProductName());
        else
            buf = sdupprintf(_("Running anaconda, the %s system installer - please wait...\n"), getProductName());
        printf("%s", buf);

        if (!(pid = fork())) {
            if (execv(anacondaArgs[0], anacondaArgs) == -1) {
               fprintf(stderr,"exec of anaconda failed: %s\n",strerror(errno));
               exit(1);
            }
        }

        waitpid(pid, &status, 0);

        if (!WIFEXITED(status) || (WIFEXITED(status) && WEXITSTATUS(status))) {
            rc = 1;
        } else {
            rc = 0;
        }

        if ((rc == 0) && (FL_POWEROFF(flags) || FL_HALT(flags))) {
            if (!(pid = fork())) {
                char * cmd = (FL_POWEROFF(flags) ? strdup("/sbin/poweroff") :
                              strdup("/sbin/halt"));
                if (execl(cmd, cmd, NULL) == -1) {
                    fprintf(stderr, "exec of poweroff failed: %s", 
                            strerror(errno));
                    exit(1);
                }
            }
            waitpid(pid, &status, 0);
        }

        stop_fw_loader(&loaderData);
        return rc;
    }
#if 0
    else {
	char **args = anacondaArgs;
	printf("would have run ");
	while (*args)
	    printf("%s ", *args++);
	printf("\n");
	printf("LANGKEY=%s\n", getenv("LANGKEY"));
	printf("LANG=%s\n", getenv("LANG"));
    }
#endif
    return 1;
}
