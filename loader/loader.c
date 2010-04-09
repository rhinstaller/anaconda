/*
 * loader.c
 *
 * This is the installer loader.  Its job is to somehow load the rest
 * of the installer into memory and run it.  This may require setting
 * up some devices and networking, etc. The main point of this code is
 * to stay SMALL! Remember that, live by that, and learn to like it.
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005,
 * 2006, 2007  Red Hat, Inc.  All rights reserved.
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
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <ctype.h>
#include <errno.h>
#include <execinfo.h>
#include <fcntl.h>
#include <newt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include <stdint.h>
#include <dirent.h>
#include <arpa/inet.h>

#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/utsname.h>

#include <linux/fb.h>
#include <linux/serial.h>
#include <linux/vt.h>

#include <glib.h>

#ifdef USE_MTRACE
#include <mcheck.h>
#endif

#include "copy.h"
#include "getparts.h"
#include "loader.h"
#include "loadermisc.h" /* JKFIXME: functions here should be split out */
#include "lang.h"
#include "fwloader.h"
#include "kbd.h"
#include "kickstart.h"
#include "windows.h"

/* module stuff */
#include "modules.h"
#include "moduleinfo.h"

#include "driverdisk.h"

/* hardware stuff */
#include "hardware.h"

/* install method stuff */
#include "method.h"
#include "cdinstall.h"
#include "nfsinstall.h"
#include "hdinstall.h"
#include "urls.h"
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
#include "../isys/log.h"

/* maximum number of extra arguments that can be passed to the second stage */
#define MAX_EXTRA_ARGS 128
static char * extraArgs[MAX_EXTRA_ARGS];
static int hasGraphicalOverride();

static int newtRunning = 0;

/* boot flags -- we need these in a lot of places */
uint64_t flags = LOADER_FLAGS_SELINUX;

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
static int init_sig = SIGUSR1; /* default to shutdown=halt */
static const char *LANG_DEFAULT = "en_US.UTF-8";

static struct installMethod installMethods[] = {
    { N_("Local CD/DVD"), 0, DEVICE_CDROM, mountCdromImage },
    { N_("Hard drive"), 0, DEVICE_DISK, mountHardDrive },
    { N_("NFS directory"), 1, DEVICE_NETWORK, mountNfsImage },
    { "URL", 1, DEVICE_NETWORK, mountUrlImage },
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

static int expected_exit = 0;

static void doExit(int) __attribute__ ((noreturn));
static void doExit(int result)
{
    expected_exit = 1;
    exit(result);
}

void doSuspend(void) {
    newtFinished();
    doExit(1);
}

void doShell(void) {
    pid_t child;
    int status;

    newtSuspend();
    child = fork();

    if (child == 0) {
        if (execl("/sbin/bash", "/sbin/bash", "-i", NULL) == -1) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
            _exit(1);
        }
    } else if (child == -1) {
        logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        newtResume();
    } else {
        if (waitpid(child, &status, 0) == -1) {
            logMessage(ERROR, "%s (%d): %m", __func__, __LINE__);
        }

        newtResume();
    }
}

void doGdbserver(struct loaderData_s *loaderData) {
    int child, fd;
    char *pid;
    iface_t iface;

    /* If gdbserver is found, go ahead and run it on the loader process now
     * before anything bad happens.
     */
    if (loaderData->gdbServer && !access("/usr/bin/gdbserver", X_OK)) {
        pid_t loaderPid = getpid();
        iface_init_iface_t(&iface);

        if (kickstartNetworkUp(loaderData, &iface)) {
            logMessage(ERROR, "can't run gdbserver due to no network");
            return;
        }

        checked_asprintf(&pid, "%d", loaderPid);

        if (!(child = fork())) {
            logMessage(INFO, "starting gdbserver: %s %s %s %s",
                       "/usr/bin/gdbserver", "--attach", loaderData->gdbServer,
                       pid);

            fd = open("/dev/null", O_RDONLY);
            close(STDIN_FILENO);
            dup2(fd, STDIN_FILENO);
            close(fd);
            fd = open("/dev/null", O_WRONLY);
            close(STDOUT_FILENO);
            dup2(fd, STDOUT_FILENO);
            close(STDERR_FILENO);
            dup2(fd, STDERR_FILENO);
            close(fd);

            if (execl("/usr/bin/gdbserver", "/usr/bin/gdbserver", "--attach",
                      loaderData->gdbServer, pid, NULL) == -1)
                logMessage(ERROR, "error running gdbserver: %m");

            _exit(1);
        }
    }
}

void startNewt(void) {
    if (!newtRunning) {
        char *buf;
        char *arch = getProductArch();
        checked_asprintf(&buf, _("Welcome to %s for %s"), getProductName(), arch);

        /*
         * Because currently initrd.img only has got the default English locale
         * support, pretend for newtInit() it is actually the used LANG so Newt
         * knows how to compute character widths etc. 
         */
        char *lang = getenv("LANG");
        if (lang) {
            lang = strdup(lang);
        }
        setenv("LANG", LANG_DEFAULT, 1);
        newtInit();
        unsetenv("LANG");
        /* restore the original LANG value */
        if (lang) {
            setenv("LANG", lang, 1);
            free(lang);
        }

        newtCls();
        newtDrawRootText(0, 0, buf);
        free(buf);
        
        newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
        
        newtRunning = 1;
        if (!access("/bin/sh",  X_OK)) 
            newtSetSuspendCallback((void *) doShell, NULL);
    }
}

void stopNewt(void) {
    if (newtRunning) newtFinished();
    newtRunning = 0;
}

static gchar *productName = NULL;
static gchar *productPath = NULL;
static gchar *productArch = NULL;

static void initProductInfo(void) {
    gchar *contents = NULL;
    gchar **lines = NULL, **stamp = NULL;
    GError *fileErr = NULL;

    if (!g_file_get_contents("/.buildstamp", &contents, NULL, &fileErr)) {
        logMessage(ERROR, "error reading .buildstamp: %s", fileErr->message);
        g_error_free(fileErr);
        productName = g_strdup("anaconda");
        productArch = g_strdup("unknown architecture");
        productPath = g_strdup("anaconda");
        return;
    }

    /* .buildstamp uses the first 3 lines in this format:
     *     STAMP.productArch
     *     productName
     *     productPath
     */
    lines = g_strsplit(contents, "\n", 0);
    g_free(contents);

    if ((lines != NULL) && (g_strv_length(lines) >= 3)) {
        /* STAMP.productArch */
        stamp = g_strsplit(lines[0], ".", 0);

        if ((stamp != NULL) && (g_strv_length(stamp) == 2)) {
            productArch = g_strdup(stamp[1]);
        } else {
            productArch = g_strdup("unknown architecture");
        }

        if (stamp) {
            g_strfreev(stamp);
        }

        productName = g_strdup(lines[1]);
        productPath = g_strdup(lines[2]);
    } else {
        productName = g_strdup("anaconda");
        productArch = g_strdup("unknown architecture");
        productPath = g_strdup("anaconda");
    }

    if (lines) {
        g_strfreev(lines);
    }

    return;
}

char * getProductName(void) {
    if (!productName) {
       initProductInfo();
    }
    return productName;
}

char * getProductArch(void) {
    if (!productArch) {
       initProductInfo();
    }
    return productArch;
}

char * getProductPath(void) {
    if (!productPath) {
       initProductInfo();
    }
    return productPath;
}

void initializeConsole() {
    /* enable UTF-8 console */
    setenv("LANG", LANG_DEFAULT, 1);
    printf("\033%%G");
    fflush(stdout);

    isysLoadFont();
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
	mknod(dev, 0600 | S_IFCHR, makedev(4, n));
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

        if (!access("/tmp/updates/pyrc.py", R_OK|X_OK))
            setenv("PYTHONSTARTUP", "/tmp/updates/pyrc.py", 1);
        else if (!access("/usr/share/anaconda/pyrc.py", R_OK|X_OK))
            setenv("PYTHONSTARTUP", "/usr/share/anaconda/pyrc.py", 1);
        setenv("LD_LIBRARY_PATH", LIBPATH, 1);
        setenv("LANG", "C", 1);
        
        if (execl("/bin/sh", "-/bin/sh", NULL) == -1) {
            logMessage(CRITICAL, "exec of /bin/sh failed: %m");
            exit(1);
        }
    }

    return;
}


static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

void loadUpdates(struct loaderData_s *loaderData) {
    char *device = NULL, *part = NULL, *buf;
    char **devNames = NULL;
    enum { UPD_DEVICE, UPD_PART, UPD_PROMPT, UPD_LOAD, UPD_DONE } stage = UPD_DEVICE;
    int rc, num = 0;
    int dir = 1;

    while (stage != UPD_DONE) {
        switch (stage) {
        case UPD_DEVICE: {
            rc = getRemovableDevices(&devNames);
            if (rc == 0)
                return;

            /* we don't need to ask which to use if they only have one */
            if (rc == 1) {
                device = strdup(devNames[0]);
                free(devNames);
                devNames = NULL;
                if (dir == -1)
                    return;

                stage = UPD_PART;
                break;
            }
            dir = 1;

            startNewt();
            rc = newtWinMenu(_("Update Disk Source"),
                             _("You have multiple devices which could serve "
                               "as sources for an update disk.  Which would "
                               "you like to use?"), 40, 10, 10,
                             rc < 6 ? rc : 6, devNames,
                             &num, _("OK"), _("Cancel"), NULL);

            if (rc == 2) {
                free(devNames);
                devNames = NULL;
                return;
            }

            device = strdup(devNames[num]);
            free(devNames);
            devNames = NULL;
            stage = UPD_PART;
        }

        case UPD_PART: {
            char ** part_list = getPartitionsList(device);
            int nump = 0, num = 0;

            if (part != NULL) {
                free(part);
                part = NULL;
            }

            if ((nump = lenPartitionsList(part_list)) == 0) {
                if (dir == -1) {
                    stage = UPD_DEVICE;
                } else {
                    checked_asprintf(&part, "/dev/%s", device);
                    stage = UPD_PROMPT;
                }

                break;
            }
            dir = 1;

            startNewt();
            rc = newtWinMenu(_("Update Disk Source"),
                             _("There are multiple partitions on this device "
                               "which could contain the update disk image.  "
                               "Which would you like to use?"), 40, 10, 10,
                             nump < 6 ? nump : 6, part_list, &num, _("OK"),
                             _("Back"), NULL);

            if (rc == 2) {
                freePartitionsList(part_list);
                stage = UPD_DEVICE;
                dir = -1;
                break;
            }

            part = strdup(part_list[num]);
            stage = UPD_LOAD;
        }

        case UPD_PROMPT:
            checked_asprintf(&buf, _("Insert your updates disk into %s and "
                                     "press \"OK\" to continue."), part);

            rc = newtWinChoice(_("Updates Disk"), _("OK"), _("Back"), buf);
            free(buf);
            buf = NULL;

            if (rc == 2) {
                stage = UPD_PART;
                dir = -1;
                break;
            }

            stage = UPD_LOAD;
            break;

        case UPD_LOAD:
            logMessage(INFO, "UPDATES device is %s", part);

            if (doPwMount(part, "/tmp/update-disk", "auto", "ro", NULL)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Failed to mount updates disk"));
                stage = UPD_PROMPT;
                break;
            } else {
                /* Copy everything to /tmp/updates so we can unmount the disk  */
                winStatus(40, 3, _("Updates"), _("Reading anaconda updates"));
                if (!copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                                   copyErrorFn)) {
                    dir = 1;
                    stage = UPD_DONE;
                }

                newtPopWindow();
                umount("/tmp/update-disk");
            }

        case UPD_DONE:
            break;
        }
    }

    return;
}

static char *newUpdatesLocation(const char *origLocation) {
    const char *location;
    char *retval = NULL;
    newtComponent f, okay, cancel, answer, locationEntry;
    newtGrid grid, buttons;

    startNewt();

    locationEntry = newtEntry(-1, -1, NULL, 60, &location, NEWT_FLAG_SCROLL);
    newtEntrySet(locationEntry, origLocation, 1);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Cancel"), &cancel, NULL);

    grid = newtCreateGrid(1, 3);

    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT,
                     newtTextboxReflowed(-1, -1, _("Unable to download the updates image.  Please modify the updates location below or press Cancel to proceed without updates.."), 60, 0, 0, 0),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, locationEntry,
                     0, 1, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 1, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Error downloading updates image"));
    newtGridFree(grid, 1);

    /* run the form */
    answer = newtRunForm(f);

    if (answer != cancel)
        retval = strdup(location);

    newtFormDestroy(f);
    newtPopWindow();

    return retval;
}

static int loadUpdatesFromRemote(char * url, struct loaderData_s * loaderData) {
    int rc = getFileFromUrl(url, "/tmp/updates.img", loaderData);

    if (rc != 0) {
        char *newLocation = newUpdatesLocation(url);

        if (!newLocation)
           return rc;
        else
           return loadUpdatesFromRemote(newLocation, loaderData);
    }

    copyUpdatesImg("/tmp/updates.img");
    unlink("/tmp/updates.img");
    return 0;
}

static void writeVNCPasswordFile(char *pfile, char *password) {
    FILE *f;

    f = fopen(pfile, "w+");
    fprintf(f, "%s\n", password);
    fclose(f);
}

/* XXX: read information from /etc/sysconfig/network-scripts/ifcfg-$INTERFACE
 * (written by linuxrc), the linuxrc mess should be firing up NM too
 */
static void readNetInfo(struct loaderData_s ** ld) {
    int i;
    struct loaderData_s * loaderData = *ld;
    DIR *dp = NULL;
    FILE *f = NULL;
    struct dirent *ent = NULL;
    char *cfgfile = NULL;
    int bufsiz = 100;
    char buf[bufsiz];
    char *vname = NULL;
    char *vparm = NULL;

    /* when this function is called, we can assume only one network device
     * config file has been written to /etc/sysconfig/network-scripts, so
     * find it and read it
     */
    dp = opendir("/etc/sysconfig/network-scripts");
    if (dp == NULL) {
        return;
    }

    while ((ent = readdir(dp)) != NULL) {
        if (!strncmp(ent->d_name, "ifcfg-", 6)) {
            checked_asprintf(&cfgfile, "/etc/sysconfig/network-scripts/%s",
                             ent->d_name);

            break;
        }
    }

    if (dp != NULL) {
        if (closedir(dp) == -1) {
            logMessage(DEBUGLVL, "%s (%d): %m", __func__, __LINE__);
            abort();
        }
    }

    if (cfgfile == NULL) {
        logMessage(DEBUGLVL, "no ifcfg files found in /etc/sysconfig/network-scripts");
        return;
    }


    if ((f = fopen(cfgfile, "r")) == NULL) {
        logMessage(DEBUGLVL, "%s (%d): %m", __func__, __LINE__);
        free(cfgfile);
        return;
    }

    if ((vname = (char *) malloc(sizeof(char) * 15)) == NULL) {
        logMessage(DEBUGLVL, "%s (%d): %m", __func__, __LINE__);
        abort();
    }

    if ((vparm = (char *) malloc(sizeof(char) * 85)) == NULL) {
        logMessage(DEBUGLVL, "%s (%d): %m", __func__, __LINE__);
        abort();
    }

    /* make sure everything is NULL before we begin copying info */
    loaderData->ipv4 = NULL;
    loaderData->netmask = NULL;
    loaderData->gateway = NULL;
    loaderData->dns = NULL;
    loaderData->peerid = NULL;
    loaderData->subchannels = NULL;
    loaderData->portname = NULL;
    loaderData->nettype = NULL;
    loaderData->ctcprot = NULL;
    loaderData->layer2 = NULL;
    loaderData->portno = NULL;
    loaderData->macaddr = NULL;
#ifdef ENABLE_IPV6
    loaderData->ipv6 = NULL;
    loaderData->gateway6 = NULL;
#endif

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

            if (!strncmp(vname, "IPADDR", 6))
                loaderData->ipv4 = strdup(vparm);

            if (!strncmp(vname, "NETMASK", 7))
                loaderData->netmask = strdup(vparm);

            if (!strncmp(vname, "GATEWAY", 7))
                loaderData->gateway = strdup(vparm);

            if (!strncmp(vname, "DNS", 3))
                loaderData->dns = strdup(vparm);

            if (!strncmp(vname, "MTU", 3)) {
                errno = 0;
                loaderData->mtu = strtol(vparm, NULL, 10);

                if ((errno == ERANGE && (loaderData->mtu == LONG_MIN ||
                                         loaderData->mtu == LONG_MAX)) ||
                    (errno != 0 && loaderData->mtu == 0)) {
                    logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                    abort();
                }
            }

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

    if (loaderData->ipv4 && loaderData->netmask) {
        flags |= LOADER_FLAGS_HAVE_CMSCONF;
    }

    if (fclose(f) == -1) {
        logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    if (cfgfile != NULL) {
        free(cfgfile);
    }

    return;
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
        loaderData->ipv4 = strndup(start, end-start);
        loaderData->ipinfo_set = 1;

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
        loaderData->ipv4 = strdup(argv + 3);
        loaderData->ipinfo_set = 1;
    }

    if (loaderData->ipinfo_set)
        flags |= LOADER_FLAGS_IP_PARAM;
}

#ifdef ENABLE_IPV6
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

    if (!strncasecmp(argv, "ipv6=dhcp", 9)) {
        loaderData->ipv6 = strdup("dhcp");
    } else if (!strncasecmp(argv, "ipv6=auto", 9)) {
        loaderData->ipv6 = strdup("auto");
    }

    if (loaderData->ipv6 != NULL) {
        loaderData->ipv6info_set = 1;
        flags |= LOADER_FLAGS_IPV6_PARAM;
    }

    return;
}
#endif

static long argToLong(char *arg, int offset) {
    long retval;

    errno = 0;

    retval = strtol(arg+offset, NULL, 10);
    if ((errno == ERANGE && (retval == LONG_MIN || retval == LONG_MAX)) ||
        (errno != 0 && retval == 0)) {
        logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    return retval;
}

/* parses /proc/cmdline for any arguments which are important to us.  
 * NOTE: in test mode, can specify a cmdline with --cmdline
 */
static void parseCmdLineFlags(struct loaderData_s * loaderData,
                              char * cmdLine) {
    int fd;
    char buf[1024];
    int len;
    gint argc = 0;
    gchar **argv = NULL;
    GError *optErr = NULL;
    int numExtraArgs = 0;
    int i;
    char *front;

    /* we want to default to graphical and allow override with 'text' */
    flags |= LOADER_FLAGS_GRAPHICAL;

    /* if we have any explicit cmdline (probably test mode), we don't want
     * to parse /proc/cmdline */
    if (!cmdLine) {
        if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return;
        len = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (len <= 0) {
            logMessage(INFO, "kernel command line was empty");
            return;
        }
        
        buf[len] = '\0';
        cmdLine = buf;
    }

    logMessage(INFO, "kernel command line: %s", cmdLine);
    
    if (!g_shell_parse_argv(cmdLine, &argc, &argv, &optErr)) {
        g_error_free(optErr);
        return;
    }

    for (i=0; i < argc; i++) {
        if (!strcasecmp(argv[i], "askmethod"))
            flags |= LOADER_FLAGS_ASKMETHOD;
        else if (!strcasecmp(argv[i], "asknetwork"))
            flags |= LOADER_FLAGS_ASKNETWORK;
        else if (!strcasecmp(argv[i], "noshell"))
            flags |= LOADER_FLAGS_NOSHELL;
        else if (!strcasecmp(argv[i], "nokill"))
            flags |= LOADER_FLAGS_NOKILL;
        else if (!strcasecmp(argv[i], "mediacheck"))
            flags |= LOADER_FLAGS_MEDIACHECK;
        else if (!strcasecmp(argv[i], "allowwireless"))
            flags |= LOADER_FLAGS_ALLOW_WIRELESS;
        else if (!strcasecmp(argv[i], "telnet"))
            flags |= LOADER_FLAGS_TELNETD;
        else if (!strcasecmp(argv[i], "noprobe"))
            flags |= LOADER_FLAGS_NOPROBE;
        else if (!strcasecmp(argv[i], "text")) {
            logMessage(INFO, "text mode forced from cmdline");
            flags |= LOADER_FLAGS_TEXT;
            flags &= ~LOADER_FLAGS_GRAPHICAL;
        }
        else if (!strcasecmp(argv[i], "graphical")) {
            logMessage(INFO, "graphical mode forced from cmdline");
            flags |= LOADER_FLAGS_GRAPHICAL;
        } else if (!strcasecmp(argv[i], "cmdline")) {
            logMessage(INFO, "cmdline mode forced from cmdline");
            flags |= LOADER_FLAGS_CMDLINE;
        } else if (!strncasecmp(argv[i], "updates=", 8))
            loaderData->updatessrc = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "updates", 7))
            flags |= LOADER_FLAGS_UPDATES;
        else if (!strncasecmp(argv[i], "dogtail=", 8))
            loaderData->dogtailurl = strdup(argv[i] + 8);
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
        else if (!strcasecmp(argv[i], "noipv4"))
            flags |= LOADER_FLAGS_NOIPV4;
#ifdef ENABLE_IPV6
        else if (!strcasecmp(argv[i], "noipv6"))
            flags |= LOADER_FLAGS_NOIPV6;
#endif
        else if (!strcasecmp(argv[i], "kssendmac"))
            flags |= LOADER_FLAGS_KICKSTART_SEND_MAC;
        else if (!strcasecmp(argv[i], "kssendsn"))
            flags |= LOADER_FLAGS_KICKSTART_SEND_SERIAL;
        /* deprecated hardware bits */
        else if (!strcasecmp(argv[i], "nousbstorage"))
            mlAddBlacklist("usb-storage");
        else if (!strcasecmp(argv[i], "nousb")) {
            mlAddBlacklist("ehci-hcd");
            mlAddBlacklist("ohci-hcd");
            mlAddBlacklist("uhci-hcd");
        } else if (!strcasecmp(argv[i], "nofirewire"))
            mlAddBlacklist("firewire-ohci");
        else if (!strncasecmp(argv[i], "loglevel=", 9)) {
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
        else if (!strncasecmp(argv[i], "method=", 7)) {
            logMessage(WARNING, "method= is deprecated.  Please use repo= instead.");
            loaderData->instRepo = strdup(argv[i] + 7);
        }
        else if (!strncasecmp(argv[i], "repo=", 5))
            loaderData->instRepo = strdup(argv[i] + 5);
        else if (!strncasecmp(argv[i], "stage2=", 7))
            setStage2LocFromCmdline(argv[i] + 7, loaderData);
        else if (!strncasecmp(argv[i], "hostname=", 9))
            loaderData->hostname = strdup(argv[i] + 9);
        else if (!strncasecmp(argv[i], "ip=", 3))
            parseCmdLineIp(loaderData, argv[i]);
#ifdef ENABLE_IPV6
        else if (!strncasecmp(argv[i], "ipv6=", 5))
            parseCmdLineIpv6(loaderData, argv[i]);
#endif
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
            loaderData->mtu = argToLong(argv[i], 4);
        else if (!strncasecmp(argv[i], "wepkey=", 7))
            loaderData->wepkey = strdup(argv[i] + 7);
        else if (!strncasecmp(argv[i], "linksleep=", 10))
            num_link_checks = argToLong(argv[i], 10);
        else if (!strncasecmp(argv[i], "nicdelay=", 9))
            post_link_sleep = argToLong(argv[i], 9);
        else if (!strncasecmp(argv[i], "dhcptimeout=", 12))
            loaderData->dhcpTimeout = argToLong(argv[i], 12);
        else if (!strncasecmp(argv[i], "selinux=0", 9))
            flags &= ~LOADER_FLAGS_SELINUX;
        else if (!strncasecmp(argv[i], "selinux", 7))
            flags |= LOADER_FLAGS_SELINUX;
        else if (!strncasecmp(argv[i], "gdb=", 4))
            loaderData->gdbServer = strdup(argv[i] + 4);
        else if (!strncasecmp(argv[i], "proxy=", 6))
            splitProxyParam(argv[i]+6, &loaderData->proxyUser,
                            &loaderData->proxyPassword, &loaderData->proxy);
        else if (numExtraArgs < (MAX_EXTRA_ARGS - 1)) {
            /* go through and append args we just want to pass on to */
            /* the anaconda script, but don't want to represent as a */
            /* LOADER_FLAGS_XXX since loader doesn't care about these */
            /* particular options.                                   */
            /* do vncpassword case first */
            if (!strncasecmp(argv[i], "vncpassword=", 12)) {
                writeVNCPasswordFile("/tmp/vncpassword.dat", argv[i]+12);
            }
            else if (!strncasecmp(argv[i], "resolution=", 11) ||
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
                if (!strncasecmp(argv[i], "vnc", 3)) {
                    logMessage(INFO, "vnc forced graphical mode from cmdline");
                    flags |= LOADER_FLAGS_GRAPHICAL;
                }

                /* the following things require networking to be configured
                 * by loader, so an active connection is ready once we get
                 * to anaconda
                 */
                if (!strncasecmp(argv[i], "syslog", 6) ||
                    !strncasecmp(argv[i], "vnc", 3)) {
                    logMessage(INFO, "early networking required for %s",
                               argv[i]);
                    flags |= LOADER_FLAGS_EARLY_NETWORKING;
                }
                if (isKickstartFileRemote(loaderData->ksFile)) {
                    logMessage(INFO, "early networking required for remote kickstart configuration");
                    flags |= LOADER_FLAGS_EARLY_NETWORKING;
                }

                if (!strncasecmp(argv[i], "vesa", 4)) {
                    checked_asprintf(&extraArgs[numExtraArgs],
                                     "--xdriver=vesa");

                    logMessage(WARNING, "\"vesa\" command line argument is deprecated.  use \"xdriver=vesa\".");
                } else {
                    checked_asprintf(&extraArgs[numExtraArgs],"--%s",
                                     argv[i]);
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

/* make sure they have enough ram */
static void checkForRam(void) {
    if (totalMemory() < MIN_RAM) {
        char *buf;

        checked_asprintf(&buf, _("You do not have enough RAM to install %s "
                                 "on this machine."), getProductName());

        startNewt();
        newtWinMessage(_("Error"), _("OK"), buf);
        free(buf);
        stopNewt();
        doExit(0);
    }
}

static int haveDeviceOfType(int type) {
    struct device ** devices;

    devices = getDevices(type);
    if (devices) {
        return 1;
    }
    return 0;
}

static char *doLoaderMain(struct loaderData_s *loaderData,
                          moduleInfoSet modInfo) {
    enum { STEP_LANG, STEP_KBD, STEP_METHOD, STEP_DRIVER,
           STEP_DRIVERDISK, STEP_NETWORK, STEP_IFACE,
           STEP_IP, STEP_STAGE2, STEP_DONE } step;

    char *url = NULL, *ret = NULL, *devName = NULL, *kbdtype = NULL;
    static iface_t iface;
    int i, rc = LOADER_NOOP, dir = 1;
    int needsNetwork = 0, class = -1;
    int skipMethodDialog = 0, skipLangKbd = 0;

    char *installNames[10];
    int numValidMethods = 0;
    int validMethods[10];

    for (i = 0; i < numMethods; i++, numValidMethods++) {
        installNames[numValidMethods] = installMethods[i].name;
        validMethods[numValidMethods] = i;
    }
    installNames[numValidMethods] = NULL;

    /* Before anything else, see if there's a CD/DVD with a stage2 image on
     * it.  However if stage2= was given, use that value as an override here.
     * That will also then bypass any method selection UI in loader.
     */
    if (!FL_ASKMETHOD(flags)) {
        url = findAnacondaCD("/mnt/stage2");
        if (url) {
            setStage2LocFromCmdline(url, loaderData);
            skipMethodDialog = 1;

            logMessage(INFO, "Detected stage 2 image on CD (url: %s)", url);
            winStatus(50, 3, _("Media Detected"),
                      _("Found local installation media"), 0);
            sleep(3);
            newtPopWindow();

            skipLangKbd = 1;
            flags |= LOADER_FLAGS_NOPASS;
        } else if (!loaderData->stage2Data && loaderData->instRepo) {
            /* If no CD/DVD with a stage2 image was found and we were given a
             * repo=/method= parameter, try to piece together a valid setting
             * for the stage2= parameter based on that.
             */
            char *tmp;

            checked_asprintf(&tmp, "%s/images/install.img",
                             loaderData->instRepo);

            logMessage(INFO, "no stage2= given, assuming %s", tmp);
            setStage2LocFromCmdline(tmp, loaderData);
            free(tmp);

            /* If we had to infer a stage2= location, but the repo= parameter
             * we based this guess on was wrong, we need to correct the typo
             * in both places.  Unfortunately we can't really know what the
             * user meant, so the best we can do is take the results of
             * running stage2= through the UI and chop off any /images/whatever
             * path that's at the end of it.
             */
            loaderData->inferredStage2 = 1;
            skipMethodDialog = 1;
        } else if (loaderData->stage2Data) {
            skipMethodDialog = 1;
        }
    } else {
        /* Needed because they have already been set when parsing cmdline.
         * (Leaks a little.)
         */
        loaderData->method = -1;
        loaderData->stage2Data = NULL;
    }

    i = 0;
    step = STEP_LANG;

    while (step != STEP_DONE) {
        switch(step) {
            case STEP_LANG: {
                if (loaderData->lang && (loaderData->lang_set == 1))
                    setLanguage(loaderData->lang, 1);
                else if (FL_RESCUE(flags) || !skipLangKbd)
                    chooseLanguage(&loaderData->lang);

                step = STEP_KBD;
                dir = 1;
                break;
            }

            case STEP_KBD: {
                if (loaderData->kbd && (loaderData->kbd_set == 1)) {
                    /* JKFIXME: this is broken -- we should tell of the 
                     * failure; best by pulling code out in kbd.c to use */
                    if (isysLoadKeymap(loaderData->kbd)) {
                        logMessage(WARNING, "requested keymap %s is not valid, asking",
                                   loaderData->kbd);
                        loaderData->kbd = NULL;
                        loaderData->kbd_set = 0;
                        break;
                    }
                    rc = LOADER_NOOP;
                } else if (FL_RESCUE(flags) || !skipLangKbd) {
                    /* JKFIXME: should handle kbdtype, too probably... but it 
                     * just matters for sparc */
                    if (!FL_CMDLINE(flags))
                        rc = chooseKeyboard(loaderData, &kbdtype);
                    else
                       rc = LOADER_NOOP;
                } else {
                    step = STEP_METHOD;
                    dir = 1;
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
            }

            case STEP_METHOD: {
                if (loaderData->method != -1)
                    skipMethodDialog = 1;
                else if (FL_CMDLINE(flags)) {
                    fprintf(stderr, "No method given for cmdline mode, aborting\n");
                    doExit(EXIT_FAILURE);
                }

                /* If we already found a stage2 image, skip the prompt. */
                if (skipMethodDialog) {
                    if (dir == 1)
                        rc = 1;
                    else
                        rc = -1;
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
                                     _("What type of media contains the installation "
                                       "image?"),
                                     30, 10, 20, 6, installNames, &loaderData->method,
                                     _("OK"), _("Back"), NULL);
                    if (rc == 2) {
                        loaderData->method = -1;
                    }
                }

                if (rc && (rc != 1)) {
                    step = STEP_KBD;
                    dir = -1;
                } else {
                    class = installMethods[validMethods[loaderData->method]].type;
                    step = STEP_DRIVER;
                    dir = 1;
                }
                break;
            }

            case STEP_DRIVER: {
                if ((FL_EARLY_NETWORKING(flags) && haveDeviceOfType(DEVICE_NETWORK)) ||
                    (class == -1 || haveDeviceOfType(class))) {
                    step = STEP_NETWORK;
                    dir = 1;
                    class = -1;
                    break;
                }

                if (skipLangKbd) {
                    skipLangKbd = 0;
                    step = STEP_KBD;
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
                    loaderData->method = -1;
                    dir = -1;
                    break;
                }

                chooseManualDriver(installMethods[validMethods[loaderData->method]].type,
                                   loaderData);
                /* it doesn't really matter what we return here; we just want
                 * to reprobe and make sure we have the driver */
                step = STEP_DRIVER;
                break;
            }

            case STEP_DRIVERDISK: {
                if (skipLangKbd) {
                    skipLangKbd = 0;
                    step = STEP_KBD;
                    break;
                }

                rc = loadDriverFromMedia(class, loaderData, 0, 0);
                if (rc == LOADER_BACK) {
                    step = STEP_DRIVER;
                    dir = -1;
                    break;
                }

                /* need to come back to driver so that we can ensure that we found
                 * the right kind of driver after loading the driver disk */
                step = STEP_DRIVER;
                break;
            }

            case STEP_NETWORK: {
                if (((installMethods[validMethods[loaderData->method]].type !=
                       DEVICE_NETWORK) && (!hasGraphicalOverride()) &&
                      !FL_ASKNETWORK(flags) &&
                      !FL_EARLY_NETWORKING(flags)) ||
                     (is_nm_connected())) {
                    needsNetwork = 0;
                    if (dir == 1) 
                        step = STEP_STAGE2;
                    else if (dir == -1)
                        step = STEP_METHOD;
                    break;
                }

                needsNetwork = 1;
                if (!haveDeviceOfType(DEVICE_NETWORK)) {
                    class = DEVICE_NETWORK;
                    step = STEP_DRIVER;
                    break;
                }
                logMessage(INFO, "need to set up networking");

                memset(&iface, 0, sizeof(iface));

                /* fall through to interface selection */
            }

            case STEP_IFACE: {
                logMessage(INFO, "going to pick interface");

                /* skip configureTCPIP() screen for kickstart (#260621) */
                if (loaderData->ksFile)
                    flags |= LOADER_FLAGS_IS_KICKSTART;

                if (FL_HAVE_CMSCONF(flags)) {
                    loaderData->ipinfo_set = 1;
#ifdef ENABLE_IPV6
                    loaderData->ipv6info_set = 1;
#endif
                }

                rc = chooseNetworkInterface(loaderData);
                if ((rc == LOADER_BACK) || (rc == LOADER_ERROR) ||
                    ((dir == -1) && (rc == LOADER_NOOP))) {
                    /* don't skip method dialog iff we don't have url from ks or boot params */
                    if (!loaderData->stage2Data) {
                        loaderData->method = -1;
                    }
                    step = STEP_METHOD;
                    dir = -1;
                    break;
                }

                devName = loaderData->netDev;
                strcpy(iface.device, devName);

                /* continue to ip config */
                step = STEP_IP;
                dir = 1;
                break;
            }

            case STEP_IP: {
                if (!needsNetwork || dir == -1) {
                    step = STEP_METHOD; /* only hit going back */
                    break;
                }

                if ((ret = malloc(INET6_ADDRSTRLEN+1)) == NULL) {
                    logMessage(ERROR, "malloc failure for ret in STEP_IP");
                    doExit(EXIT_FAILURE);
                }

                logMessage(INFO, "going to do getNetConfig");

                /* s390 provides all config info by way of the CMS conf file */
                if (FL_HAVE_CMSCONF(flags)) {
                    loaderData->ipinfo_set = 1;
#ifdef ENABLE_IPV6
                    loaderData->ipv6info_set = 1;
#endif
                }

                /* populate netDev based on any kickstart data */
                setupIfaceStruct(&iface, loaderData);
                rc = readNetConfig(devName, &iface, loaderData->netCls, loaderData->method);

                /* set the hostname if we have that */
                if (loaderData->hostname) {
                    if (sethostname(loaderData->hostname,
                                    strlen(loaderData->hostname))) {
                        logMessage(ERROR, "error setting hostname to %s",
                                   loaderData->hostname);
                    }
                }

                free(ret);
                ret = NULL;

                if ((rc == LOADER_BACK) ||
                    ((dir == -1) && (rc == LOADER_NOOP))) {
                    needsNetwork = 1;
                    step = STEP_IFACE;
                    dir = -1;
                    break;
                }
                /* retry */
                if (rc == LOADER_ERROR) {
                    needsNetwork = 1;
                    break;
                }

                writeEnabledNetInfo(&iface);
                step = STEP_STAGE2;
                dir = 1;
                break;
            }

            case STEP_STAGE2: {
                if (url) {
                    logMessage(INFO, "stage2 url is %s", url);
                    return url;
                }

                logMessage(INFO, "starting STEP_STAGE2");
                url = installMethods[validMethods[loaderData->method]].mountImage(
                                          installMethods + validMethods[loaderData->method],
                                          "/mnt/stage2", loaderData);
                if (!url) {
                    step = STEP_IP;
                    loaderData->ipinfo_set = 0;
#ifdef ENABLE_IPV6
                    loaderData->ipv6info_set = 0;
#endif
                    loaderData->method = -1;
                    skipMethodDialog = 0;
                    dir = -1;
                } else {
                    logMessage(INFO, "got stage2 at url %s", url);
                    step = STEP_DONE;
                    dir = 1;

                    if (loaderData->invalidRepoParam) {
                        char *newInstRepo;

                        /* Doesn't contain /images?  Let's not even try. */
                        if (strstr(url, "/images") == NULL)
                            break;
                        
                        checked_asprintf(&newInstRepo, "%.*s",
                                         (int) (strstr(url, "/images")-url), url);

                        free(loaderData->instRepo);
                        loaderData->instRepo = newInstRepo;
                        logMessage(INFO, "reset repo= parameter to %s",
                                   loaderData->instRepo);
                    }
                }

                break;
            }

            case STEP_DONE:
                break;
        }
    }

    return url;
}
static int manualDeviceCheck(struct loaderData_s *loaderData) {
    char ** devices;
    int i, j, rc, num = 0;
    unsigned int width = 40;
    char * buf;

    do {
        /* FIXME */
        devices = malloc(1 * sizeof(*devices));
        j = 0;
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

        chooseManualDriver(DEVICE_ANY, loaderData);
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

    checked_asprintf(&runtimedir, "/mnt/runtime%s", dirname);

    if (!access(runtimedir, X_OK)) {
        if (unlink(dirname) == -1) {
            char * olddir;
            
            checked_asprintf(&olddir, "%s_old", dirname);

            ret = rename(dirname, olddir);
            free(olddir);
        }
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
    void *array[30];
    size_t i;
    const char const * const errmsgs[] = {
        "loader received SIG",
        "!  Backtrace:\n",
        "Loader exited unexpectedly!  Backtrace:\n",
    };

    /* XXX This should really be in a glibc header somewhere... */
    extern const char *const sys_sigabbrev[NSIG];

    signal(signum, SIG_DFL); /* back to default */

    newtFinished();
    if (signum == 0) {
        i = write(STDERR_FILENO, errmsgs[2], strlen(errmsgs[2]));
    } else {
        i = write(STDERR_FILENO, errmsgs[0], strlen(errmsgs[0]));
        i = write(STDERR_FILENO, sys_sigabbrev[signum],
                strlen(sys_sigabbrev[signum]));
        i = write(STDERR_FILENO, errmsgs[1], strlen(errmsgs[1]));
    }

    i = backtrace (array, 30);
    backtrace_symbols_fd(array, i, STDERR_FILENO);
    _exit(1);
}

void loaderExitHandler(void)
{
    if (expected_exit)
        return;

    loaderSegvHandler(0);    
}

static void setupBacktrace(void)
{
    void *array;

    signal(SIGSEGV, loaderSegvHandler);
    signal(SIGABRT, loaderSegvHandler);
    atexit(loaderExitHandler);

    /* Turns out, there's an initializer at the top of backtrace() that
     * (on some arches) calls dlopen(). dlopen(), unsurprisingly, calls
     * malloc(). So, call backtrace() early in signal handler setup so
     * we can later safely call it from the signal handler itself. */
    backtrace(&array, 1);
}

void loaderUsrXHandler(int signum) {
    logMessage(INFO, "Remembering signal %d\n", signum);
    init_sig = signum;
}

static int anaconda_trace_init(void) {
#ifdef USE_MTRACE
    setenv("MALLOC_TRACE","/malloc",1);
    mtrace();
#endif
    /* We have to do this before we init bogl(), which doLoaderMain will do
     * when setting fonts for different languages.  It's also best if this
     * is well before we might take a SEGV, so they'll go to tty8 */
    initializeTtys();

    /* set up signal handler */
    setupBacktrace();

    return 0;
}

static void add_to_path_env(const char *env, const char *val)
{
    char *oldenv, *newenv;

    oldenv = getenv(env);
    if (oldenv) {
        checked_asprintf(&newenv, "%s:%s", val, oldenv);

        oldenv = strdupa(newenv);
        free(newenv);
        newenv = oldenv;
    } else {
        newenv = strdupa(val);
    }

    setenv(env, newenv, 1);
}

static void loadScsiDhModules(void)
{
    struct utsname utsname;
    char *modules = NULL;
    char *tmp = NULL;
    struct dirent *ent = NULL;

    uname(&utsname);
    checked_asprintf(&tmp,
        "/lib/modules/%s/kernel/drivers/scsi/device_handler", utsname.release);

    DIR *dir = opendir(tmp);
    free(tmp);
    if (!dir)
        return;

    int fd = dirfd(dir);
    while ((ent = readdir(dir)) != NULL) {
        struct stat sb;

        if (fstatat(fd, ent->d_name, &sb, 0) < 0)
            continue;

        size_t len = strlen(ent->d_name) - 3;
        if (strcmp(ent->d_name+len, ".ko"))
            continue;

        if (S_ISREG(sb.st_mode)) {
            char modname[len+1];
            strncpy(modname, ent->d_name, len);
	    modname[len] = '\0';

            if (modules && modules[0]) {
                checked_asprintf(&tmp, "%s:%s", modules, modname);
            } else {
                checked_asprintf(&tmp, "%s", modname);
            }

            free(modules);
            modules = tmp;
        }
    }
    closedir(dir);

    mlLoadModuleSet(modules);
    free(modules);
}

int main(int argc, char ** argv) {
    int rc, ret, pid, status;

    struct stat sb;
    struct serial_struct si;
    char * arg;
    FILE *f;

    char twelve = 12;

    moduleInfoSet modInfo;

    char *url = NULL;

    char ** argptr, ** tmparg;
    char * anacondaArgs[50];

    struct loaderData_s loaderData;

    char *path, *fmt;
    GSList *dd, *dditer;

    gchar *cmdLine = NULL, *ksFile = NULL, *virtpcon = NULL;
    gboolean mediacheck = FALSE;
    gchar **remaining = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry optionTable[] = {
        { "cmdline", 0, 0, G_OPTION_ARG_STRING, &cmdLine, NULL, NULL },
        { "ksfile", 0, 0, G_OPTION_ARG_STRING, &ksFile, NULL, NULL },
        { "mediacheck", 0, 0, G_OPTION_ARG_NONE, &mediacheck, NULL, NULL },
        { "virtpconsole", 0, 0, G_OPTION_ARG_STRING, &virtpcon, NULL, NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
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

    /* Very first thing, set up tracebacks and debug features. */
    rc = anaconda_trace_init();

    /* now we parse command line options */
    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, optionTable, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        fprintf(stderr, "bad option: %s\n", optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        doExit(1);
    }

    g_option_context_free(optCon);

    if (remaining) {
        fprintf(stderr, "unexpected argument: %s\n", remaining[0]);
        g_strfreev(remaining);
        doExit(1);
    }

    g_strfreev(remaining);

    if (!access("/var/run/loader.run", R_OK)) {
        printf(_("loader has already been run.  Starting shell.\n"));
        execl("/bin/sh", "-/bin/sh", NULL);
        doExit(0);
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

    if (mediacheck) flags |= LOADER_FLAGS_MEDIACHECK;
    if (ksFile) flags |= LOADER_FLAGS_KICKSTART;
    if (virtpcon) flags |= LOADER_FLAGS_VIRTPCONSOLE;

    /* uncomment to send mac address in ks=http:/ header by default*/
    flags |= LOADER_FLAGS_KICKSTART_SEND_MAC;

    /* JKFIXME: I do NOT like this... it also looks kind of bogus */
#if defined(__s390__) || defined(__s390x__)
    flags |= LOADER_FLAGS_NOSHELL;
#endif

    openLog();
    
    /* XXX if RHEL, enable the AUTODD feature by default,
     * but we should come with more general way how to control this */
    if (!strncmp(getProductName(), "Red Hat", 7)) {
        flags |= LOADER_FLAGS_AUTOMODDISK;
    }

    memset(&loaderData, 0, sizeof(loaderData));
    loaderData.method = -1;
    loaderData.fw_loader_pid = -1;
    loaderData.fw_search_pathz_len = -1;
    loaderData.dhcpTimeout = -1;

    extraArgs[0] = NULL;
    parseCmdLineFlags(&loaderData, cmdLine);

    logMessage(INFO, "anaconda version %s on %s starting", VERSION, getProductArch());

    if ((FL_SERIAL(flags) || FL_VIRTPCONSOLE(flags)) && 
        !hasGraphicalOverride()) {
        logMessage(INFO, "text mode forced due to serial/virtpconsole");
        flags |= LOADER_FLAGS_TEXT;
    }
    set_fw_search_path(&loaderData, "/firmware:/lib/firmware");
    start_fw_loader(&loaderData);

    arg = "/lib/modules/module-info";
    modInfo = newModuleInfoSet();
    if (readModuleInfo(arg, modInfo, NULL, 0)) {
        fprintf(stderr, "failed to read %s\n", arg);
        sleep(5);
        stop_fw_loader(&loaderData);
        doExit(1);
    }
    initializeConsole();

    checkForRam();

    /* iSeries vio console users will be ssh'ing in to the primary
       partition, so use a terminal type that is appripriate */
    if (isVioConsole())
        setenv("TERM", "vt100", 1);

    mlLoadModuleSet("cramfs:squashfs:iscsi_tcp");

    loadScsiDhModules();

#if !defined(__s390__) && !defined(__s390x__)
    mlLoadModuleSet("floppy:edd:pcspkr:iscsi_ibft");
#endif

#ifdef ENABLE_IPV6
    if (!FL_NOIPV6(flags))
        mlLoadModule("ipv6", NULL);
#endif

    /* now let's do some initial hardware-type setup */
#if defined(__powerpc__)
    mlLoadModule("spufs", NULL);
#endif

    if (loaderData.lang && (loaderData.lang_set == 1)) {
        setLanguage(loaderData.lang, 1);
    }

    /* FIXME: this is a bit of a hack */
    loaderData.modInfo = modInfo;

    /* Setup depmod & modprobe so we can load multiple DDs */
    modprobeDDmode();

    /* If there is /.rundepmod file present, rerun depmod */
    if (!access("/.rundepmod", R_OK)){
        if (system("depmod -a")) {
            /* this is not really fatal error, it might still work, log it */
            logMessage(ERROR, "Error running depmod -a for initrd overlay");
        }
    }

    if (FL_AUTOMODDISK(flags)) {
        /* Load all autodetected DDs */
        logMessage(INFO, "Trying to detect vendor driver discs");
        dd = findDriverDiskByLabel();
        dditer = dd;
        while(dditer) {
            /* load the DD */
            if (loadDriverDiskFromPartition(&loaderData, (char*)(dditer->data))) {
                logMessage(ERROR, "Automatic driver disk loader failed for %s.", (char*)(dditer->data));
            }
            else {
                logMessage(INFO, "Automatic driver disk loader succeeded for %s.", (char*)(dditer->data));
            }
            
            /* clean the device record */
            free((char*)(dditer->data));
            dditer->data = NULL;

            /* next DD */
            dditer = g_slist_next(dditer);
        }
        g_slist_free(dd);
    }

    if (FL_MODDISK(flags)) {
        startNewt();
        loadDriverDisks(DEVICE_ANY, &loaderData);
    }

    if (!access("/dd.img", R_OK)) {
        logMessage(INFO, "found /dd.img, loading drivers");
        getDDFromSource(&loaderData, "path:/dd.img");
    }
    
    /* Reset depmod & modprobe to normal mode and get the rest of drivers*/
    modprobeNormalmode();

    /* this allows us to do an early load of modules specified on the
     * command line to allow automating the load order of modules so that
     * eg, certain scsi controllers are definitely first.
     * FIXME: this syntax is likely to change in a future release
     *        but is done as a quick hack for the present.
     */
    if (!mlInitModuleConfig()) {
        logMessage(ERROR, "unable to initialize kernel module loading");
        abort();
    }

    earlyModuleLoad(0);

    busProbe(FL_NOPROBE(flags));

    /* Disable all network interfaces in NetworkManager by default */
#if !defined(__s390__) && !defined(__s390x__)
    int i;

    if ((i = writeDisabledNetInfo()) != 0) {
        logMessage(ERROR, "writeDisabledNetInfo failure: %d", i);
    }
#endif

    /* Start NetworkManager now so it's always available to talk to. */
    if (iface_start_NetworkManager())
        logMessage(INFO, "failed to start NetworkManager");

    if (!FL_CMDLINE(flags))
        startNewt();

    /* can't run gdbserver until after network modules are loaded */
    doGdbserver(&loaderData);

    /* JKFIXME: we'd really like to do this before the busprobe, but then
     * we won't have network devices available (and that's the only thing
     * we support with this right now */
    if (loaderData.ddsrc != NULL) {
        getDDFromSource(&loaderData, loaderData.ddsrc);
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
        startTelnetd(&loaderData);

    url = doLoaderMain(&loaderData, modInfo);

    /* unlink dirs and link to the ones in /mnt/runtime */
    migrate_runtime_directory("/usr");
    migrate_runtime_directory("/lib");
    migrate_runtime_directory("/lib64");
    ret = symlink("/mnt/runtime/etc/selinux", "/etc/selinux");
    copyDirectory("/mnt/runtime/etc","/etc", NULL, copyErrorFn);
    copyDirectory("/mnt/runtime/var","/var", NULL, copyErrorFn);

    /* now load SELinux policy before exec'ing anaconda and the shell
     * (if we're using SELinux) */
    if (FL_SELINUX(flags)) {
        if (mount("/selinux", "/selinux", "selinuxfs", 0, NULL)) {
            logMessage(ERROR, "failed to mount /selinux: %m, disabling SELinux");
            flags &= ~LOADER_FLAGS_SELINUX;
        } else {
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

    if (FL_NOPROBE(flags) && !loaderData.ksFile) {
        startNewt();
        manualDeviceCheck(&loaderData);
    }

    if (loaderData.updatessrc)
        loadUpdatesFromRemote(loaderData.updatessrc, &loaderData);
    else if (FL_UPDATES(flags))
        loadUpdates(&loaderData);

    /* make sure /tmp/updates exists so that magic in anaconda to */
    /* symlink rhpl/ will work                                    */
    if (access("/tmp/updates", F_OK))
        mkdirChain("/tmp/updates");

    add_fw_search_dir(&loaderData, "/tmp/updates/firmware");
    add_fw_search_dir(&loaderData, "/tmp/product/firmware");

    add_to_path_env("PYTHONPATH", "/tmp/updates");
    add_to_path_env("PYTHONPATH", "/tmp/updates/iw");
    add_to_path_env("PYTHONPATH", "/tmp/updates/textw");
    add_to_path_env("PYTHONPATH", "/tmp/product");
    add_to_path_env("LD_LIBRARY_PATH", "/tmp/updates");
    add_to_path_env("LD_LIBRARY_PATH", "/tmp/product");
    add_to_path_env("PATH", "/tmp/updates");
    add_to_path_env("PATH", "/tmp/product");

    stop_fw_loader(&loaderData);
    start_fw_loader(&loaderData);

    mlLoadModuleSet("raid0:raid1:raid5:raid6:raid456:raid10:linear:dm-mod:dm-zero:dm-mirror:dm-snapshot:dm-multipath:dm-round-robin:dm-crypt:cbc:sha256:lrw:xts");

    if (!access("/mnt/runtime/usr/lib/libunicode-lite.so.1", R_OK))
        setenv("LD_PRELOAD", "/mnt/runtime/usr/lib/libunicode-lite.so.1", 1);
    if (!access("/mnt/runtime/usr/lib64/libunicode-lite.so.1", R_OK))
        setenv("LD_PRELOAD", "/mnt/runtime/usr/lib64/libunicode-lite.so.1", 1);

    argptr = anacondaArgs;

    path = getenv("PATH");
    while (path && path[0]) {
        int n = strcspn(path, ":");
        char c, *binpath;

        c = path[n];
        path[n] = '\0';
        checked_asprintf(&binpath, "%s/anaconda", path);
        path[n] = c;

        if (!access(binpath, X_OK)) {
            *argptr++ = strdupa(binpath);
            free(binpath);
            break;
        }
        free(binpath);
        path += n + 1;
    }

    logMessage(INFO, "Running anaconda script %s", *(argptr-1));

    *argptr++ = "--stage2";
    if (strncmp(url, "ftp:", 4)) {
        *argptr++ = url;
    } else {
        int fd, ret;

        fd = open("/tmp/ftp-stage2", O_CREAT | O_TRUNC | O_RDWR, 0600);
        ret = write(fd, url, strlen(url));
        ret = write(fd, "\r", 1);
        close(fd);
        *argptr++ = "@/tmp/ftp-stage2";
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

#ifdef ENABLE_IPV6
    if (FL_NOIPV6(flags))
        *argptr++ = "--noipv6";
#endif

#if defined(__s390__) || defined(__s390x__)
    *argptr++ = "--headless";
#endif

    if (FL_KICKSTART(flags)) {
        *argptr++ = "--kickstart";
        *argptr++ = loaderData.ksFile;
    }

    if (FL_SERIAL(flags))
        *argptr++ = "--serial";

    if (FL_RESCUE(flags)) {
        *argptr++ = "--rescue";
    } else {
        if (FL_TEXT(flags))
            *argptr++ = "-T";
        else if (FL_GRAPHICAL(flags))
            *argptr++ = "--graphical";
        if (FL_CMDLINE(flags))
            *argptr++ = "-C";
        if (!FL_SELINUX(flags))
            *argptr++ = "--noselinux";
        else if (FL_SELINUX(flags))
            *argptr++ = "--selinux";

        if (FL_VIRTPCONSOLE(flags)) {
            *argptr++ = "--virtpconsole";
            *argptr++ = virtpcon;
        }

        if (loaderData.updatessrc && FL_UPDATES(flags)) {
            *argptr++ = "--updates";
            *argptr++ = loaderData.updatessrc;
        }

        if (loaderData.dogtailurl) {
            *argptr++ = "--dogtail";
            *argptr++ = loaderData.dogtailurl;
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

        if (loaderData.instRepo) {
           *argptr++ = "--repo";
            if (strncmp(loaderData.instRepo, "ftp:", 4)) {
                *argptr++ = loaderData.instRepo;
            } else {
                int fd, ret;

                fd = open("/tmp/ftp-repo", O_CREAT | O_TRUNC | O_RDWR, 0600);
                ret = write(fd, loaderData.instRepo, strlen(loaderData.instRepo));
                ret = write(fd, "\r", 1);
                close(fd);
                *argptr++ = "@/tmp/ftp-repo";
            }
        }

        if (loaderData.proxy && strcmp("", loaderData.proxy)) {
            *argptr++ = "--proxy";

            *argptr++ = strdup(loaderData.proxy);

            if (loaderData.proxyUser && strcmp(loaderData.proxyUser, "")) {
                int fd, ret;

                fd = open("/tmp/proxy", O_CREAT|O_TRUNC|O_RDWR, 0600);
                ret = write(fd, loaderData.proxyUser, strlen(loaderData.proxyUser));
                ret = write(fd, "\r\n", 2);

                if (loaderData.proxyPassword && strcmp(loaderData.proxyPassword, "")) {
                    ret = write(fd, loaderData.proxyPassword, strlen(loaderData.proxyPassword));
                    ret = write(fd, "\r\n", 2);
                }

                close(fd);

                *argptr++ = "--proxyAuth";
                *argptr++ = "/tmp/proxy";
            }
        }
    }
    
    *argptr = NULL;
    
    stopNewt();
    closeLog();

    if (FL_RESCUE(flags)) {
        fmt = _("Running anaconda %s, the %s rescue mode - please wait.\n");
    } else {
        fmt = _("Running anaconda %s, the %s system installer - please wait.\n");
    }
    printf(fmt, VERSION, getProductName());

    if (!(pid = fork())) {
        if (execv(anacondaArgs[0], anacondaArgs) == -1) {
           fprintf(stderr,"exec of anaconda failed: %m\n");
           doExit(1);
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
                fprintf(stderr, "exec of poweroff failed: %m\n");
                doExit(1);
            }
        }
        waitpid(pid, &status, 0);
    }

    stop_fw_loader(&loaderData);
#if defined(__s390__) || defined(__s390x__)
    /* at the latest possibility signal init=linuxrc.s390 to reboot/halt */
    logMessage(INFO, "Sending signal %d to process %d\n",
               init_sig, init_pid);
    kill(init_pid, init_sig);
#endif
    doExit(rc);

    doExit(1);
}

/* vim:set sw=4 sts=4 et: */
