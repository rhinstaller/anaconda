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
 * Copyright 1997 - 2002 Red Hat, Inc.
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
#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <syslog.h>
#include <unistd.h>

#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>

#include <linux/fb.h>

#include "loader.h"
#include "loadermisc.h" /* JKFIXME: functions here should be split out */
#include "log.h"
#include "lang.h"
#include "kbd.h"
#include "kickstart.h"
#include "windows.h"

/* module stuff */
#include "modules.h"
#include "moduleinfo.h"
#include "moduledeps.h"
#include "modstubs.h"

#include "driverdisk.h"

/* hardware stuff */
#include "hardware.h"
#include "firewire.h"
#include "pcmcia.h"
#include "usb.h"

/* install method stuff */
#include "method.h"
#include "cdinstall.h"
#include "nfsinstall.h"
#include "hdinstall.h"
#include "urlinstall.h"

#include "telnetd.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/probe.h"
#include "../isys/stubs.h"
#include "../isys/lang.h"

/* maximum number of extra arguments that can be passed to the second stage */
#define MAX_EXTRA_ARGS 128

static int newtRunning = 0;


#ifdef INCLUDE_LOCAL
#include "cdinstall.h"
#include "hdinstall.h"
#endif
#ifdef INCLUDE_NETWORK
#include "nfsinstall.h"
#include "urlinstall.h"
#endif

static struct installMethod installMethods[] = {
#if defined(INCLUDE_LOCAL)
    { N_("Local CDROM"), "cdrom", 0, CLASS_CDROM, mountCdromImage },
    { N_("Hard drive"), "hd", 0, CLASS_HD, mountHardDrive },
#endif
#if defined(INCLUDE_NETWORK)
    { N_("NFS image"), "nfs", 1, CLASS_NETWORK, mountNfsImage },
    { "FTP", "ftp", 1, CLASS_NETWORK, mountUrlImage },
    { "HTTP", "http", 1, CLASS_NETWORK, mountUrlImage },
#endif
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

/* JKFIXME: bad hack for second stage modules without module-info */
struct moduleBallLocation * secondStageModuleLocation;
    

#if 0
#if !defined(__s390__) && !defined(__s390x__)
#define RAMDISK_DEVICE "/dev/ram"
#else
#define RAMDISK_DEVICE "/dev/ram2"
#endif


int setupRamdisk(void) {
    gzFile f;
    static int done = 0;

    if (done) return 0;

    done = 1;

    f = gunzip_open("/etc/ramfs.img");
    if (f) {
        char buf[10240];
        int i, j = 0;
        int fd;
        
        fd = open(RAMDISK_DEVICE, O_RDWR);
        logMessage("copying file to fd %d", fd);
        
        while ((i = gunzip_read(f, buf, sizeof(buf))) > 0) {
            j += write(fd, buf, i);
        }
        
        logMessage("wrote %d bytes", j);
        close(fd);
        gunzip_close(f);
    }
    
    if (doPwMount(RAMDISK_DEVICE, "/tmp/ramfs", "ext2", 0, 0, NULL, NULL))
        logMessage("failed to mount ramfs image");
    
    return 0;
}
#endif

void setupRamfs(void) {
    mkdirChain("/tmp/ramfs");
    doPwMount("none", "/tmp/ramfs", "ramfs", 0, 0, NULL, NULL);
}


void doSuspend(void) {
    newtFinished();
    exit(1);
}

void startNewt(int flags) {
    if (!newtRunning) {
        char *buf = sdupprintf(_("Welcome to %s"), PRODUCTNAME);
        newtInit();
        newtCls();
        newtDrawRootText(0, 0, buf);
        free(buf);
        
        newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
        
        newtRunning = 1;
        if (FL_TESTING(flags)) 
            newtSetSuspendCallback((void *) doSuspend, NULL);
    }
}

void stopNewt(void) {
    if (newtRunning) newtFinished();
    newtRunning = 0;
}

void initializeConsole(moduleList modLoaded, moduleDeps modDeps,
                       moduleInfoSet modInfo, int flags) {
    if (!FL_NOFB(flags))
	mlLoadModuleSet("vga16fb", modLoaded, modDeps, modInfo, flags);
    /* enable UTF-8 console */
    printf("\033%%G");
    fflush(stdout);
    isysLoadFont();
    if (!FL_TESTING(flags))
        isysSetUnicodeKeymap();
}

static void spawnShell(int flags) {
    pid_t pid;
    int fd;

    if (FL_SERIAL(flags) || FL_NOSHELL(flags)) {
        logMessage("not spawning a shell");
        return;
    }

    fd = open("/dev/tty2", O_RDWR);
    if (fd < 0) {
        logMessage("cannot open /dev/tty2 -- no shell will be provided");
        return;
    } else if (access("/bin/sh",  X_OK))  {
        logMessage("cannot open shell - /bin/sh doesn't exist");
        return;
    }
    
    if (!(pid = fork())) {
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
            logMessage("could not set new controlling tty");
        }
        
        signal(SIGINT, SIG_DFL);
        signal(SIGTSTP, SIG_DFL);
        
        setenv("LD_LIBRARY_PATH",
               "/lib:/usr/lib:/usr/X11R6/lib:/mnt/usr/lib:"
               "/mnt/sysimage/lib:/mnt/sysimage/usr/lib", 1);
        
        execl("/bin/sh", "-/bin/sh", NULL);
        logMessage("exec of /bin/sh failed: %s", strerror(errno));
        exit(1);
    }
    
    close(fd);

    return;
}

void loadUpdates(struct knownDevices *kd, int flags) {
    int done = 0;
    int rc;
    char * device = NULL, ** devNames = NULL;
    char * buf;
    int num = 0;

    startNewt(flags);

    do { 
        rc = getRemovableDevices(&devNames);
        if (rc == 0) 
            return;
        startNewt(flags);
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
        device = strdup(devNames[num]);
        free(devNames);


        buf = sdupprintf(_("Insert your updates disk into /dev/%s and press "
                           "\"OK\" to continue."), device);
        rc = newtWinChoice(_("Updates Disk"), _("OK"), _("Cancel"), buf);
        if (rc == 2)
            return;

        logMessage("UPDATES device is %s", device);

        devMakeInode(device, "/tmp/upd.disk");
        if (doPwMount("/tmp/upd.disk", "/tmp/update-disk", "ext2", 1, 0, 
                      NULL, NULL) && 
            doPwMount("/tmp/upd.disk", "/tmp/update-disk", "iso9660", 1, 0,
                      NULL, NULL)) {
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

static void checkForHardDrives(struct knownDevices * kd, int * flagsPtr) {
    int i;
    int flags = (*flagsPtr);

    for (i = 0; i < kd->numKnown; i++)
        if (kd->known[i].class == CLASS_HD) break;

    if (i != kd->numKnown) 
        return;

    startNewt(flags);
    i = newtWinChoice(_("Warning"), _("Yes"), _("No"),
                      _("No hard drives have been found.  You probably need "
                        "to manually choose device drivers for the "
                        "installation to succeed.  Would you like to "
                        "select drivers now?"));
    if (i != 2) (*flagsPtr) = (*flagsPtr) | LOADER_FLAGS_ISA;

    return;
}


/* parses /proc/cmdline for any arguments which are important to us.  
 * NOTE: in test mode, can specify a cmdline with --cmdline
 */
static int parseCmdLineFlags(int flags, struct loaderData_s * loaderData,
                             char * cmdLine, char * extraArgs[]) {
    int fd;
    char buf[500];
    int len;
    char ** argv;
    int argc;
    int numExtraArgs = 0;
    int i;

    /* if we have any explicit cmdline (probably test mode), we don't want
     * to parse /proc/cmdline */
    if (!cmdLine) {
        if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return flags;
        len = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (len <= 0) return flags;
        
        buf[len] = '\0';
        cmdLine = buf;
    }
    
    if (poptParseArgvString(cmdLine, &argc, (const char ***) &argv))
        return flags;

    for (i=0; i < argc; i++) {
        if (!strcasecmp(argv[i], "expert"))
            flags |= (LOADER_FLAGS_EXPERT | LOADER_FLAGS_MODDISK | 
                      LOADER_FLAGS_ASKMETHOD);
        else if (!strcasecmp(argv[i], "askmethod"))
            flags |= LOADER_FLAGS_ASKMETHOD;
        else if (!strcasecmp(argv[i], "noshell"))
            flags |= LOADER_FLAGS_NOSHELL;
        else if (!strcasecmp(argv[i], "mediacheck"))
            flags |= LOADER_FLAGS_MEDIACHECK;
        else if (!strcasecmp(argv[i], "nousbstorage"))
            flags |= LOADER_FLAGS_NOUSBSTORAGE;
        else if (!strcasecmp(argv[i], "nousb"))
            flags |= LOADER_FLAGS_NOUSB;
        else if (!strcasecmp(argv[i], "telnet"))
            flags |= LOADER_FLAGS_TELNETD;
        else if (!strcasecmp(argv[i], "nofirewire"))
            flags |= LOADER_FLAGS_NOIEEE1394;
        else if (!strcasecmp(argv[i], "noprobe"))
            flags |= LOADER_FLAGS_NOPROBE;
        else if (!strcasecmp(argv[i], "nopcmcia"))
            flags |= LOADER_FLAGS_NOPCMCIA;
        else if (!strcasecmp(argv[i], "text"))
            flags |= LOADER_FLAGS_TEXT;
        else if (!strcasecmp(argv[i], "updates"))
            flags |= LOADER_FLAGS_UPDATES;
        else if (!strcasecmp(argv[i], "isa"))
            flags |= LOADER_FLAGS_ISA;
        else if (!strcasecmp(argv[i], "dd"))
            flags |= LOADER_FLAGS_MODDISK;
        else if (!strcasecmp(argv[i], "driverdisk"))
            flags |= LOADER_FLAGS_MODDISK;
        else if (!strcasecmp(argv[i], "rescue"))
            flags |= LOADER_FLAGS_RESCUE;
        else if (!strcasecmp(argv[i], "nopass"))
            flags |= LOADER_FLAGS_NOPASS;
        else if (!strcasecmp(argv[i], "serial")) 
            flags |= LOADER_FLAGS_SERIAL;
        else if (!strcasecmp(argv[i], "nofb"))
            flags |= LOADER_FLAGS_NOFB;
        else if (!strncasecmp(argv[i], "debug=", 6))
            setLogLevel(strtol(argv[i] + 6, (char **)NULL, 10));
        else if (!strncasecmp(argv[i], "ksdevice=", 9)) {
            loaderData->netDev = strdup(argv[i] + 9);
            loaderData->netDev_set = 1;
        }
        else if (!strcasecmp(argv[i], "ks") || !strncasecmp(argv[i], "ks=", 3))
            loaderData->ksFile = strdup(argv[i]);
        else if (!strncasecmp(argv[i], "display=", 8))
            setenv("DISPLAY", argv[i] + 8, 1);
        else if ((!strncasecmp(argv[i], "lang=", 5)) && 
                 (strlen(argv[i]) > 5))  {
            loaderData->lang = strdup(argv[i] + 5);
            loaderData->lang_set = 1;
        } else if (!strncasecmp(argv[i], "keymap=", 7) &&
                   (strlen(argv[i]) > 7)) {
            loaderData->kbd = strdup(argv[i] + 7);
            loaderData->kbd_set = 1;
        } else if (!strncasecmp(argv[i], "method=", 7)) {
            char * c;
            loaderData->method = strdup(argv[i] + 7);

            c = loaderData->method;
            /* : will let us delimit real information on the method */
            if ((c = strtok(c, ":"))) {
                c = strtok(NULL, ":");
                /* JKFIXME: handle other methods too, and not here... */
                if (!strcmp(loaderData->method, "nfs")) {
                    loaderData->methodData = calloc(sizeof(struct nfsInstallData *), 1);
                    ((struct nfsInstallData *)loaderData->methodData)->host = c;
                    if ((c = strtok(NULL, ":"))) {
                        ((struct nfsInstallData *)loaderData->methodData)->directory = c;
                    }
                }
            }
        } else if (!strncasecmp(argv[i], "ip=", 3)) {
            loaderData->ip = strdup(argv[i] + 3);
            loaderData->ipinfo_set = 1;
        } else if (!strncasecmp(argv[i], "netmask=", 8)) 
            loaderData->netmask = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "gateway=", 8))
            loaderData->gateway = strdup(argv[i] + 8);
        else if (!strncasecmp(argv[i], "dns=", 4))
            loaderData->dns = strdup(argv[i] + 4);
        else if (numExtraArgs < (MAX_EXTRA_ARGS - 1)) {
            /* go through and append args we just want to pass on to */
            /* the anaconda script, but don't want to represent as a */
            /* LOADER_FLAG_XXX since loader doesn't care about these */
            /* particular options.                                   */
            if (!strncasecmp(argv[i], "resolution=", 11) ||
                !strncasecmp(argv[i], "lowres", 6) ||
                !strncasecmp(argv[i], "skipddc", 7) ||
                !strncasecmp(argv[i], "nomount", 7)) {
                int arglen;

                arglen = strlen(argv[i])+3;
                extraArgs[numExtraArgs] = (char *) malloc(arglen*sizeof(char));
                snprintf(extraArgs[numExtraArgs], arglen, "--%s", argv[i]);
                numExtraArgs = numExtraArgs + 1;
        
                if (numExtraArgs > (MAX_EXTRA_ARGS - 2)) {
                    logMessage("Too many command line arguments (max allowed is %s), "
                               "rest will be dropped.", MAX_EXTRA_ARGS);
                }
            }
        }
    }

    /* NULL terminates the array of extra args */
    extraArgs[numExtraArgs] = NULL;

    return flags;
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

/* look for available memory.  note: won't ever report more than the 
 * 900 megs or so supported by the -BOOT kernel due to not using e820 */
static int totalMemory(void) {
    int fd;
    int bytesRead;
    char buf[4096];
    char * chptr, * start;
    int total = 0;
    
    fd = open("/proc/meminfo", O_RDONLY);
    if (fd < 0) {
        logMessage("failed to open /proc/meminfo: %s", strerror(errno));
        return 0;
    }
    
    bytesRead = read(fd, buf, sizeof(buf) - 1);
    if (bytesRead < 0) {
        logMessage("failed to read from /proc/meminfo: %s", strerror(errno));
        close(fd);
        return 0;
    }
    
    close(fd);
    buf[bytesRead] = '\0';
    
    chptr = buf;
    while (*chptr && !total) {
        if (*chptr != '\n' || strncmp(chptr + 1, "MemTotal:", 9)) {
            chptr++;
            continue;
        }

        start = ++chptr ;
        while (*chptr && *chptr != '\n') chptr++;

        *chptr = '\0';
    
        while (!isdigit(*start) && *start) start++;
        if (!*start) {
            logMessage("no number appears after MemTotal tag");
            return 0;
        }

        chptr = start;
        while (*chptr && isdigit(*chptr)) {
            total = (total * 10) + (*chptr - '0');
            chptr++;
        }
    }

    logMessage("%d kB are available", total);
    
    return total;
}

/* make sure they have enough ram */
static void checkForRam(int flags) {
    if (totalMemory() < MIN_RAM) {
        char *buf;
        buf = sdupprintf(_("You do not have enough RAM to install %s "
                           "on this machine."), PRODUCTNAME);
        startNewt(flags);
        newtWinMessage(_("Error"), _("OK"), buf);
        free(buf);
        stopNewt();
        exit(0);
    }
}

/* fsm for the basics of the loader. */
static char *doLoaderMain(char * location,
                          struct loaderData_s * loaderData,
                          struct knownDevices * kd,
                          moduleInfoSet modInfo,
                          moduleList modLoaded,
                          moduleDeps * modDepsPtr,
                          int flags) {
    enum { STEP_LANG, STEP_KBD, STEP_METHOD, STEP_DRIVER, 
           STEP_DRIVERDISK, STEP_URL, STEP_DONE } step;
    char * url = NULL;
    int dir = 1;
    int rc, i;

    char * installNames[10]; /* 10 install methods will be enough for anyone */
    int numValidMethods = 0;
    int validMethods[10];
    int methodNum = -1;

    char * kbdtype = NULL;

    for (i = 0; i < numMethods; i++, numValidMethods++) {
        installNames[numValidMethods] = _(installMethods[i].name);
        validMethods[numValidMethods] = i;

        /* have we preselected this to be our install method? */
        if (loaderData->method && 
            !strcmp(loaderData->method, installMethods[i].shortname)) {
            methodNum = numValidMethods;
        }
    }

    installNames[numValidMethods] = NULL;

    /* check to see if we have a Red Hat Linux CD.  If we have one, then
     * we can fast-path the CD and not make people answer questions in 
     * text mode.  */
    if (!FL_ASKMETHOD(flags) && !FL_KICKSTART(flags)) {
        url = findRedHatCD(location, kd, modInfo, modLoaded, * modDepsPtr, flags);
        if (url && !FL_RESCUE(flags)) return url;
    }

    startNewt(flags);

    step = STEP_LANG;

    while (step != STEP_DONE) {
        switch(step) {
        case STEP_LANG:
            if (loaderData->lang && (loaderData->lang_set == 1)) {
                setLanguage(loaderData->lang, flags);
            } else {
                chooseLanguage(&loaderData->lang, flags);
            }
            step = STEP_KBD;
            dir = 1;
            break;
        case STEP_KBD:
            if (loaderData->kbd && (loaderData->kbd_set == 1)) {
                /* JKFIXME: this is broken -- we should tell of the 
                 * failure; best by pulling code out in kbd.c to use */
                if (isysLoadKeymap(loaderData->kbd)) {
                    logMessage("requested keymap %s is not valid, asking", loaderData->kbd);
                    loaderData->kbd = NULL;
                    loaderData->kbd_set = 0;
                    break;
                }
                rc = LOADER_NOOP;
            } else {
                /* JKFIXME: should handle kbdtype, too probably... but it 
                 * just matters for sparc */
                rc = chooseKeyboard(&loaderData->kbd, &kbdtype, flags);
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
             * to short-circuit to the CD */
            if (FL_RESCUE(flags) && url)
                return url;

            if (loaderData->method && (methodNum != -1)) {
                rc = 1;
            } else {
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
                step = STEP_DRIVER;
                dir = 1;
            }
            break;

        case STEP_DRIVER: {
            int found = 0;

            for (i = 0; i < kd->numKnown; i++) {
                if (installMethods[validMethods[methodNum]].deviceType == 
                    kd->known[i].class)
                    found = 1;
            }
            
            if (found) {
                step = STEP_URL;
                dir = 1;
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
                                    modLoaded, modDepsPtr, modInfo, kd, flags);
            /* it doesn't really matter what we return here; we just want
             * to reprobe and make sure we have the driver */
            step = STEP_DRIVER;
            break;
        }

        case STEP_DRIVERDISK:

            rc = loadDriverFromMedia(installMethods[validMethods[methodNum]].deviceType,
                                     modLoaded, modDepsPtr, modInfo, kd, 
                                     flags, 0);
            if (rc == LOADER_BACK) {
                step = STEP_DRIVER;
                dir = -1;
                break;
            }

            /* need to come back to driver so that we can ensure that we found
             * the right kind of driver after loading the driver disk */
            step = STEP_DRIVER;
            break;
            
        case STEP_URL:
            logMessage("starting to STEP_URL");
            url = installMethods[validMethods[methodNum]].mountImage(
                                      installMethods + validMethods[methodNum],
                                      location, kd, loaderData, modInfo, modLoaded, 
                                      modDepsPtr, flags);
            if (!url) {
                step = STEP_METHOD;
                dir = -1;
            } else {
                logMessage("got url %s", url);
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

static int manualDeviceCheck(moduleInfoSet modInfo, moduleList modLoaded,
                             moduleDeps * modDepsPtr, struct knownDevices * kd,
                             int flags) {
    char ** devices;
    int i, j, rc, num = 0;
    struct moduleInfo * mi;
    int width = 40;
    char * buf;

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
        buf = _("No device drivers have been loaded for your system.  Would "
                "you like to load any now?");
    }

    do { 
        rc = newtWinMenu(_("Devices"), buf, width, 10, 20, 
                         (j > 6) ? 6 : j, devices, &num, _("Done"), 
                         _("Add Device"), NULL);
        if (rc != 2)
            break;

        chooseManualDriver(CLASS_UNSPEC, modLoaded, modDepsPtr, modInfo, 
                           kd, flags);
    } while (1);
    return 0;
}


int main(int argc, char ** argv) {
    int flags = 0;
    struct stat sb;
    int rc, i;
    char * arg;

    char twelve = 12;
    char * extraArgs[MAX_EXTRA_ARGS];

    struct knownDevices kd;
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
    poptContext optCon;
    struct poptOption optionTable[] = {
	{ "cmdline", '\0', POPT_ARG_STRING, &cmdLine, 0 },
        { "ksfile", '\0', POPT_ARG_STRING, &ksFile, 0 },
        { "test", '\0', POPT_ARG_NONE, &testing, 0 },
        { "mediacheck", '\0', POPT_ARG_NONE, &mediacheck, 0},
        { 0, 0, 0, 0, 0 }
    };


    /* JKFIXME: very very bad hack */
    secondStageModuleLocation = malloc(sizeof(struct moduleBallLocation));
    secondStageModuleLocation->path = strdup("/mnt/runtime/modules/modules.cgz");
    
    if (!strcmp(argv[0] + strlen(argv[0]) - 6, "insmod"))
        return ourInsmodCommand(argc, argv);
    if (!strcmp(argv[0] + strlen(argv[0]) - 8, "modprobe"))
        return ourInsmodCommand(argc, argv);
    if (!strcmp(argv[0] + strlen(argv[0]) - 5, "rmmod"))
        return combined_insmod_main(argc, argv);
    
    /* The fstat checks disallows serial console if we're running through
       a pty. This is handy for Japanese. */
    fstat(0, &sb);
    if (major(sb.st_rdev) != 3 && major(sb.st_rdev) != 136) {
        if (ioctl (0, TIOCLINUX, &twelve) < 0)
            flags |= LOADER_FLAGS_SERIAL;
    }

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

    if (testing) flags |= LOADER_FLAGS_TESTING;
    if (mediacheck) flags |= LOADER_FLAGS_MEDIACHECK;

    /* JKFIXME: I do NOT like this... it also looks kind of bogus */
#if defined(__s390__) && !defined(__s390x__)
    flags |= LOADER_FLAGS_NOSHELL | LOADER_FLAGS_NOUSB;
#endif

    openLog(FL_TESTING(flags));
    if (!FL_TESTING(flags))
        openlog("loader", 0, LOG_LOCAL0);

    memset(&loaderData, 0, sizeof(loaderData));

    extraArgs[0] = NULL;
    flags = parseCmdLineFlags(flags, &loaderData, cmdLine, extraArgs);

    if (FL_SERIAL(flags) && !getenv("DISPLAY"))
        flags |= LOADER_FLAGS_TEXT;

    setupRamfs();

    arg = FL_TESTING(flags) ? "./module-info" : "/modules/module-info";
    modInfo = newModuleInfoSet();

    if (readModuleInfo(arg, modInfo, NULL, 0)) {
        fprintf(stderr, "failed to read %s\n", arg);
        sleep(5);
        exit(1);
    }

    kd = kdInit();
    mlReadLoadedList(&modLoaded);
    modDeps = mlNewDeps();
    mlLoadDeps(&modDeps, "/modules/modules.dep");

    initializeConsole(modLoaded, modDeps, modInfo, flags);
    checkForRam(flags);

    mlLoadModuleSet("cramfs:vfat:nfs:loop", modLoaded, modDeps, 
                    modInfo, flags);

    /* now let's do some initial hardware-type setup */
    ideSetup(modLoaded, modDeps, modInfo, flags, &kd);
    scsiSetup(modLoaded, modDeps, modInfo, flags, &kd);

    /* Note we *always* do this. If you could avoid this you could get
       a system w/o USB keyboard support, which would be bad. */
    usbInitialize(modLoaded, modDeps, modInfo, flags);
    
    /* now let's initialize any possible firewire.  fun */
    firewireInitialize(modLoaded, modDeps, modInfo, flags);

    /* JKFIXME: this is kind of a different way to handle pcmcia... I think
     * it's more correct, although it will require a little bit of kudzu
     * hacking */
    /*pcmciaInitialize(modLoaded, modDeps, modInfo, flags);*/

    kdFindIdeList(&kd, 0);
    kdFindScsiList(&kd, 0);
    kdFindNetList(&kd, 0);

    /* explicitly read this to let libkudzu know we want to merge
     * in future tables rather than replace the initial one */
    pciReadDrivers("/modules/pcitable");

    if ((access("/proc/bus/pci/devices", R_OK) &&
         access("/proc/openprom", R_OK) &&
         access("/proc/iSeries", R_OK)) || FL_MODDISK(flags)) {
        startNewt(flags);

        loadDriverDisks(CLASS_UNSPEC, modLoaded, &modDeps, 
                        modInfo, &kd, flags);
    }

    busProbe(modInfo, modLoaded, modDeps, 0, &kd, flags);

    /* JKFIXME: loaderData->ksFile is set to the arg from the command line,
     * and then getKickstartFile() changes it and sets FL_KICKSTART.  
     * kind of weird. */
    if (loaderData.ksFile) {
        logMessage("getting kickstart file");
        getKickstartFile(&kd, &loaderData, &flags);
        if (FL_KICKSTART(flags) && 
            (ksReadCommands(loaderData.ksFile) != LOADER_ERROR)) {
            setupKickstart(&loaderData, &flags);
        }
    }

    if (FL_TELNETD(flags))
        startTelnetd(&kd, &loaderData, modInfo, modLoaded, modDeps, flags);

    url = doLoaderMain("/mnt/source", &loaderData, &kd, modInfo, modLoaded, &modDeps, flags);

    if (!FL_TESTING(flags)) {
        unlink("/usr");
        symlink("/mnt/runtime/usr", "/usr");
        unlink("/lib");
        symlink("/mnt/runtime/lib", "/lib");
        if (!access("/mnt/runtime/lib64", X_OK)) {
            unlink("/lib64");
            symlink("/mnt/runtime/lib64", "/lib64");
        }
    }

    logMessage("getting ready to spawn shell now");
    
    spawnShell(flags);  /* we can attach gdb now :-) */

    /* setup the second stage modules; don't over-ride any already existing
     * modules because that would be rude 
     */
    {
        mlLoadDeps(&modDeps, "/mnt/runtime/modules/modules.dep");
        pciReadDrivers("/mnt/runtime/modules/pcitable");
        readModuleInfo("/mnt/runtime/modules/module-info", modInfo,
                       secondStageModuleLocation, 0);
    }

    /* JKFIXME: kickstart devices crap... probably kind of bogus now though */


    /* we might have already loaded these, but trying again doesn't hurt */
    ideSetup(modLoaded, modDeps, modInfo, flags, &kd);
    scsiSetup(modLoaded, modDeps, modInfo, flags, &kd);
    busProbe(modInfo, modLoaded, modDeps, 0, &kd, flags);

    checkForHardDrives(&kd, &flags);

    if (((access("/proc/bus/pci/devices", R_OK) &&
          access("/proc/openprom", R_OK) &&
          access("/proc/iSeries", R_OK)) ||
         FL_ISA(flags) || FL_NOPROBE(flags)) && !loaderData.ksFile) {
        startNewt(flags);
        manualDeviceCheck(modInfo, modLoaded, &modDeps, &kd, flags);
    }
    

    if (FL_UPDATES(flags)) 
        loadUpdates(&kd, flags);

    /* look for cards which require the agpgart module */
    agpgartInitialize(modLoaded, modDeps, modInfo, flags);

    mlLoadModuleSetLocation("raid0:raid1:raid5:msdos:ext3:reiserfs:jfs:xfs:lvm-mod",
			    modLoaded, modDeps, modInfo, flags, 
			    secondStageModuleLocation);

    initializeParallelPort(modLoaded, modDeps, modInfo, flags);

    usbInitializeMouse(modLoaded, modDeps, modInfo, flags);

    /* we've loaded all the modules we're going to.  write out a file
     * describing which scsi disks go with which scsi adapters */
    writeScsiDisks(modLoaded);

    /* we only want to use RHupdates on nfs installs.  otherwise, we'll 
     * use files on the first iso image and not be able to umount it */
    if (!strncmp(url, "nfs:", 4)) {
        logMessage("NFS install method detected, will use RHupdates/");
        useRHupdates = 1;
    } else {
        useRHupdates = 0;
    }

    if (useRHupdates) 
        setenv("PYTHONPATH", "/tmp/updates:/mnt/source/RHupdates", 1);
    else
        setenv("PYTHONPATH", "/tmp/updates", 1);

    if (!access("/mnt/runtime/usr/lib/libunicode-lite.so.1", R_OK))
        setenv("LD_PRELOAD", "/mnt/runtime/usr/lib/libunicode-lite.so.1", 1);

    argptr = anacondaArgs;

    if (!access("/tmp/updates/anaconda", X_OK))
        *argptr++ = "/tmp/updates/anaconda";
    else if (useRHupdates && !access("/mnt/source/RHupdates/anaconda", X_OK))
        *argptr++ = "/mnt/source/RHupdates/anaconda";
    else
        *argptr++ = "/usr/bin/anaconda";

    logMessage("Running anaconda script %s", *(argptr-1));
    
    *argptr++ = "-m";
    if (strncmp(url, "ftp:", 4)) {
        *argptr++ = url;
    } else {
        int fd;

        fd = open("/tmp/method", O_CREAT | O_TRUNC | O_RDWR, 0600);
        write(fd, url, strlen(url));
        write(fd, "\r", 1);
        close(fd);
        *argptr++ = "@/tmp/method";
    }

    /* add extra args - this potentially munges extraArgs */
    tmparg = extraArgs;
    while (*tmparg) {
        char *idx;
        
        logMessage("adding extraArg %s", *tmparg);
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
    
    if (FL_RESCUE(flags)) {
        *argptr++ = "--rescue";
    } else {
        if (FL_SERIAL(flags))
            *argptr++ = "--serial";
        if (FL_TEXT(flags))
            *argptr++ = "-T";
        if (FL_EXPERT(flags))
            *argptr++ = "--expert";
        
        if (FL_KICKSTART(flags)) {
            *argptr++ = "--kickstart";
            *argptr++ = loaderData.ksFile;
        }

        if ((loaderData.lang) && !FL_NOPASS(flags)) {
            *argptr++ = "--lang";
            *argptr++ = loaderData.lang;
        }
        
        if ((loaderData.kbd) && !FL_NOPASS(flags)) {
            *argptr++ = "--keymap";
            *argptr++ = loaderData.kbd;
        }
        
        for (i = 0; i < modLoaded->numModules; i++) {
            struct moduleInfo * mi;
            char * where;

            if (!modLoaded->mods[i].path) continue;
            
            mi = findModuleInfo(modInfo, modLoaded->mods[i].name);
            if (!mi) continue;
            if (mi->major == DRIVER_NET)
                where = "net";
            else if (mi->major == DRIVER_SCSI)
                where = "scsi";
            else
                continue;
            
            *argptr++ = "--module";
            *argptr = alloca(80);
            sprintf(*argptr, "%s:%s:%s", modLoaded->mods[i].path, where,
                    modLoaded->mods[i].name);
            
            argptr++;
        }
    }
    
    *argptr = NULL;
    
    stopNewt();
    closeLog();
    
    if (!FL_TESTING(flags)) {
        char *buf = sdupprintf(_("Running anaconda, the %s system installer - please wait...\n"), PRODUCTNAME);
        printf("%s", buf);
    	execv(anacondaArgs[0], anacondaArgs);
        perror("exec");
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
