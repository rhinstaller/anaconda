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
#include "windows.h"

/* module stuff */
#include "modules.h"
#include "moduleinfo.h"
#include "moduledeps.h"
#include "modstubs.h"

/* hardware stuff */
#include "firewire.h"
#include "pcmcia.h"
#include "usb.h"

/* install method stuff */
#include "method.h"
#include "cdinstall.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/probe.h"
#include "../isys/stubs.h"

/* maximum number of extra arguments that can be passed to the second stage */
#define MAX_EXTRA_ARGS 128

static int newtRunning = 0;


/* JKFIXME: just temporarily here.  need to move to header files for 
 * each install method */
#ifdef INCLUDE_LOCAL
char * mountCdromImage(struct installMethod * method,
                              char * location, struct knownDevices * kd,
                              moduleInfoSet modInfo, moduleList modLoaded,
                              moduleDeps * modDepsPtr, int flags);
char * mountHardDrive(struct installMethod * method,
                             char * location, struct knownDevices * kd,
                             moduleInfoSet modInfo, moduleList modLoaded,
                             moduleDeps * modDepsPtr, int flags);
#endif
#ifdef INCLUDE_NETWORK
char * mountNfsImage(struct installMethod * method,
                            char * location, struct knownDevices * kd,
                            moduleInfoSet modInfo, moduleList modLoaded,
                            moduleDeps * modDepsPtr, int flags);
char * mountUrlImage(struct installMethod * method,
                            char * location, struct knownDevices * kd,
                            moduleInfoSet modInfo, moduleList modLoaded,
                            moduleDeps * modDepsPtr, int flags);
#endif

static struct installMethod installMethods[] = {
#if defined(INCLUDE_LOCAL)
    { N_("Local CDROM"), 0, CLASS_CDROM, mountCdromImage },
#endif
#if defined(INCLUDE_NETWORK)
    { N_("NFS image"), 1, CLASS_NETWORK, mountNfsImage },
    { "FTP", 1, CLASS_NETWORK, mountUrlImage },
    { "HTTP", 1, CLASS_NETWORK, mountUrlImage },
#endif
#if 0
#if defined(INCLUDE_LOCAL)
    { N_("Hard drive"), 0, CLASS_HD, mountHardDrive },
#endif
#endif
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

/* JKFIXME: bad hack for second stage modules without module-info */
struct moduleBallLocation * secondStageModuleLocation;
    

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

    startNewt(flags);

    do { 
        rc = newtWinChoice(_("Updates Disk"), _("OK"), _("Cancel"),
                           _("Insert your updates disk and press "
                             "\"OK\" to continue."));

        if (rc == 2) return;

        /* JKFIXME: handle updates from floppy or cd */
        return;
#if 0
        logMessage("UPDATES floppy device is %s", floppyDevice);

        devMakeInode(floppyDevice, "/tmp/floppy");
        if (doPwMount("/tmp/floppy", "/tmp/update-disk", "ext2", 1, 0, NULL, 
                      NULL)) {
            newtWinMessage(_("Error"), _("OK"), 
                           _("Failed to mount floppy disk."));
        } else {
            /* Copy everything to /tmp/updates so .so files don't get run
               from /dev/floppy. We could (and probably should) get smarter 
               about this at some point. */
            winStatus(40, 3, _("Updates"), _("Reading anaconda updates..."));
            if (!copyDirectory("/tmp/update-disk", "/tmp/updates")) done = 1;
            newtPopWindow();
            umount("/tmp/update-disk");
        }
#endif
    } while (!done);
    
    return;
}

static void checkForHardDrives(struct knownDevices * kd, int flags) {
    int i;

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
    if (i != 2) flags |= LOADER_FLAGS_ISA;

    if (((access("/proc/bus/devices", R_OK) &&
          access("/proc/openprom", R_OK) &&
          access("/proc/iSeries", R_OK)) ||
         FL_ISA(flags) || FL_NOPROBE(flags)) && !FL_KICKSTART(flags)) {
        /* JKFIXME: do a manual device load */
    }
    
    return;
}

static int detectHardware(moduleInfoSet modInfo, 
              char *** modules, int flags) {
    struct device ** devices, ** device;
    char ** modList;
    int numMods;
    char *driver;
    
    logMessage("probing buses");
    
    devices = probeDevices(CLASS_UNSPEC,
                           BUS_PCI | BUS_SBUS,
                           PROBE_ALL);

    logMessage("finished bus probing");

    if (devices == NULL) {
        *modules = NULL;
        return LOADER_OK;
    }

    numMods = 0;
    for (device = devices; *device; device++) numMods++;

    if (!numMods) {
        *modules = NULL;
        return LOADER_OK;
    }
    
    modList = malloc(sizeof(*modList) * (numMods + 1));
    numMods = 0;
    
    for (device = devices; *device; device++) {
        driver = (*device)->driver;
        if (strcmp (driver, "ignore") && strcmp (driver, "unknown")
            && strcmp (driver, "disabled")) {
            modList[numMods++] = strdup(driver);
        }
        
        freeDevice (*device);
    }
    
    modList[numMods] = NULL;
    *modules = modList;
    
    free(devices);
    
    return LOADER_OK;
}

static int agpgartInitialize(moduleList modLoaded, moduleDeps modDeps,
			     moduleInfoSet modInfo, int flags) {
    struct device ** devices, *p;
    int i;

    if (FL_TESTING(flags)) return 0;

    logMessage("looking for video cards requiring agpgart module");
    
    devices = probeDevices(CLASS_VIDEO, BUS_UNSPEC, PROBE_ALL);
    
    if (!devices) {
        logMessage("no video cards found");
        return 0;
    }

    /* loop thru cards, see if we need agpgart */
    for (i=0; devices[i]; i++) {
        p = devices[i];
        logMessage("found video card controller %s", p->driver);
        
        /* HACK - need to have list of cards which match!! */
        if (!strcmp(p->driver, "Card:Intel 810") ||
            !strcmp(p->driver, "Card:Intel 815")) {
            logMessage("found %s card requiring agpgart, loading module",
                       p->driver+5);
            
            if (mlLoadModuleSetLocation("agpgart", modLoaded, modDeps, 
					modInfo, flags, 
					secondStageModuleLocation)) {
                logMessage("failed to insert agpgart module");
                return 1;
            } else {
                /* only load it once! */
                return 0;
            }
        }
    }
    
    return 0;
}

/* This loads the necessary parallel port drivers for printers so that
   kudzu can autodetect and setup printers in post install*/
static void initializeParallelPort(moduleList modLoaded, moduleDeps modDeps,
				   moduleInfoSet modInfo, int flags) {
    /* JKFIXME: this can be used on other arches too... */
#if !defined (__i386__)
    return;
#endif
    if (FL_NOPARPORT(flags)) return;

    logMessage("loading parallel port drivers...");
    if (mlLoadModuleSetLocation("parport_pc", modLoaded, modDeps, 
				modInfo, flags,
				secondStageModuleLocation)) {
        logMessage("failed to load parport_pc module");
        return;
    }
}

int busProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
             int justProbe, struct knownDevices * kd, int flags) {
    int i;
    char ** modList;
    char modules[1024];
    
    if (FL_NOPROBE(flags)) return 0;
    
    if (!access("/proc/bus/pci/devices", R_OK) ||
        !access("/proc/openprom", R_OK)) {
        /* autodetect whatever we can */
        if (detectHardware(modInfo, &modList, flags)) {
            logMessage("failed to scan pci bus!");
            return 0;
        } else if (modList && justProbe) {
            for (i = 0; modList[i]; i++)
                printf("%s\n", modList[i]);
        } else if (modList) {
            *modules = '\0';
            
            for (i = 0; modList[i]; i++) {
                if (i) strcat(modules, ":");
                strcat(modules, modList[i]);
            }
            
            mlLoadModuleSet(modules, modLoaded, modDeps, modInfo, flags);
            
            kdFindScsiList(kd, 0);
            kdFindNetList(kd, 0);
        } else 
            logMessage("found nothing");
    }
    
    return 0;
}



/* JKFIXME: move all of this hardware setup stuff to a new file */
static void scsiSetup(moduleList modLoaded, moduleDeps modDeps,
                      moduleInfoSet modInfo, int flags,
                      struct knownDevices * kd) {
    mlLoadModuleSet("sd_mod:sr_mod", modLoaded, modDeps, modInfo, flags);
}

static void ideSetup(moduleList modLoaded, moduleDeps modDeps,
                     moduleInfoSet modInfo, int flags,
                     struct knownDevices * kd) {
    
    /* This is fast enough that we don't need a screen to pop up */
    mlLoadModuleSet("ide-cd", modLoaded, modDeps, modInfo, flags);
    
    /* JKFIXME: I removed a kdFindIde() call here...  it seems bogus */
}



/* parses /proc/cmdline for any arguments which are important to us.  
 * NOTE: in test mode, can specify a cmdline with --cmdline
 */
static int parseCmdLineFlags(int flags, char * cmdLine, char * extraArgs[]) {
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
        else if (!strncasecmp(argv[i], "debug=", 6))
            setLogLevel(strtol(argv[i] + 6, (char **)NULL, 10));
        /*JKFIXME: add back kickstart stuff */
        else if (!strncasecmp(argv[i], "ksdevice=", 9))
            /* JKFIXME: *ksDevice = argv[i] + 9; */
            argv[i] + 9;
        else if (!strncasecmp(argv[i], "display=", 8))
            setenv("DISPLAY", argv[i] + 8, 1);
        /* JKFIXME: handle lang= somehow */
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
                          struct knownDevices * kd,
                          moduleInfoSet modInfo,
                          moduleList modLoaded,
                          moduleDeps modDeps,
                          int flags) {
    enum { STEP_LANG, STEP_KBD, STEP_METHOD, STEP_DRIVER, 
           STEP_URL, STEP_DONE } step;
    char * url = NULL;
    int dir = 1;
    int rc, i;

    char * installNames[10]; /* 10 install methods will be enough for anyone */
    int numValidMethods = 0;
    int validMethods[10];
    int methodNum;

    char *lang = NULL;
    char * keymap = NULL;
    char * kbdtype = NULL;

    /* JKFIXME: if this were the old code, we'd do checking about local
     * vs network install methods here.  do we still want to do that or 
     * just nuke that code? */
    for (i = 0; i < numMethods; i++) {
        installNames[numValidMethods] = _(installMethods[i].name);
        validMethods[numValidMethods++] = i;
    }

    installNames[numValidMethods] = NULL;

    /* check to see if we have a Red Hat Linux CD.  If we have one, then
     * we can fast-path the CD and not make people answer questions in 
     * text mode.  */
    /* JKFIXME: what should we do about rescue mode here? */
    if (!FL_ASKMETHOD(flags) && !FL_KICKSTART(flags)) {
        /* JKFIXME: this might not work right... */
        url = findRedHatCD(location, kd, modInfo, modLoaded, modDeps, flags);
        if (url) return url;
    }

    startNewt(flags);

    step = STEP_LANG;

    while (step != STEP_DONE) {
        switch(step) {
        case STEP_LANG:
            chooseLanguage(&lang, flags);
            /* JKFIXME: default lang stuff so that we only sometimes pass lang? */
            step = STEP_KBD;
            dir = 1;
            break;
        case STEP_KBD:
            rc = chooseKeyboard(&keymap, &kbdtype, flags);
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
            rc = newtWinMenu(FL_RESCUE(flags) ? _("Rescue Method") :
                             _("Installation Method"),
                             FL_RESCUE(flags) ?
                             _("What type of media contains the rescue "
                               "image?") :
                             _("What type of media contains the packages to "
                               "be installed?"),
                             30, 10, 20, 6, installNames, &methodNum, 
                             _("OK"), _("Back"), NULL);
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

            /* JKFIXME: this is the nifty cool new step */
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
            
            /* JKFIXME: pop up driver stuff */
            logMessage("would have gone to ask about a driver... but the code's not written, so falling back ;-)");
            step = STEP_METHOD;
            dir = -1;
            break;
        }
            
        case STEP_URL:
            logMessage("starting to STEP_URL");
            url = installMethods[validMethods[methodNum]].mountImage(
                                      installMethods + validMethods[methodNum],
                                      location, kd, modInfo, modLoaded, 
                                      &modDeps, flags);
            logMessage("got url %s", url);
            if (!url) {
                step = STEP_METHOD;
                dir = -1;
            } else {
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

int main(int argc, char ** argv) {
    int flags = 0;
    int haveKon = 0; /* JKFIXME: this should be conditionalized... */
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

    char * cmdLine = NULL;
    char * ksFile = NULL;
    int testing = 0;
    int probeOnly; /* JKFIXME: this option can probably die */
    int mediacheck = 0;
    poptContext optCon;
    struct poptOption optionTable[] = {
            { "cmdline", '\0', POPT_ARG_STRING, &cmdLine, 0 },
        { "ksfile", '\0', POPT_ARG_STRING, &ksFile, 0 },
        { "probe", '\0', POPT_ARG_NONE, &probeOnly, 0 },
        { "test", '\0', POPT_ARG_NONE, &testing, 0 },
        { "mediacheck", '\0', POPT_ARG_NONE, &mediacheck, 0},
        { 0, 0, 0, 0, 0 }
    };


    /* JKFIXME: very very bad hack */
    secondStageModuleLocation = malloc(sizeof(struct moduleBallLocation));
    secondStageModuleLocation->path = strdup("/mnt/runtime/modules/modules.cgz");
    


    /* JKFIXME: need to do multiplex command stuff for insmod, etc here */
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
    

    if (!(FL_TESTING(flags))) {
        int fd;

        fd = open("/tmp/modules.conf", O_WRONLY | O_CREAT, 0666);
        if (fd < 0) {
            logMessage("error creating /tmp/modules.conf: %s\n",
                       strerror(errno));
        } else {
            /* HACK */
#ifdef __sparc__
            write(fd, "alias parport_lowlevel parport_ax\n", 34);
#else
            write(fd, "alias parport_lowlevel parport_pc\n", 34);
#endif
            close(fd);
        }
    }            


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

    if (checkFrameBuffer() == 1) haveKon = 0;

    /* JKFIXME: I do NOT like this... it also looks kind of bogus */
#if defined(__s390__) && !defined(__s390x__)
    flags |= LOADER_FLAGS_NOSHELL | LOADER_FLAGS_NOUSB;
#endif

    openLog(FL_TESTING(flags));
    if (!FL_TESTING(flags))
	openlog("loader", 0, LOG_LOCAL0);

    extraArgs[0] = NULL;
    flags = parseCmdLineFlags(flags, cmdLine, extraArgs);

    if (FL_SERIAL(flags) && !getenv("DISPLAY"))
        flags |= LOADER_FLAGS_TEXT;

    checkForRam(flags);

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

    /* JKFIXME: this is where we used to setFloppyDevice and do KS_FLOPPY */
    
    /* JKFIXME: this is kind of a different way to handle pcmcia... I think
     * it's more correct, although it will require a little bit of kudzu
     * hacking */
    pcmciaInitialize(modLoaded, modDeps, modInfo, flags);

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
        /* JKFIXME: do the driver disk thing here for an isa machine.  bah. */
    }

    busProbe(modInfo, modLoaded, modDeps, probeOnly, &kd, flags);

    /* JKFIXME: all sorts of crap to handle kickstart sources now... */

    /* JKFIXME: telnetd */

    url = doLoaderMain("/mnt/source", &kd, modInfo, modLoaded, modDeps, flags);

    if (!FL_TESTING(flags)) {
        unlink("/usr");
        symlink("/mnt/runtime/usr", "/usr");
        unlink("/lib");
        symlink("/mnt/runtime/lib", "/lib");
        if (!access("/mnt/runtime/lib64", X_OK)) {
            unlink("/lib64");
            symlink("/mnt/runtime/lib64", "/lib64");
        }

        /* JKFIXME: need to pull in the second stage modules and use
         * them to update module-info, pcitable, etc just like with 
         * driver disks */
    }

    logMessage("getting ready to spawn shell now");
    
    spawnShell(flags);  /* we can attach gdb now :-) */

    /* setup the second stage modules; don't over-ride any already existing
     * modules because that would be rude 
     */
    {
        mlLoadDeps(&modDeps, "/mnt/runtime/modules/modules.dep");
        pciReadDrivers("/modules/pcitable");
        readModuleInfo("/mnt/runtime/modules/module-info", modInfo,
                       secondStageModuleLocation, 0);
    }

    /* JKFIXME: kickstart devices crap... probably kind of bogus now though */


    /* we might have already loaded these, but trying again doesn't hurt */
    ideSetup(modLoaded, modDeps, modInfo, flags, &kd);
    scsiSetup(modLoaded, modDeps, modInfo, flags, &kd);
    busProbe(modInfo, modLoaded, modDeps, 0, &kd, flags);

    checkForHardDrives(&kd, flags);

    if (FL_UPDATES(flags)) 
        loadUpdates(&kd, flags);

    /* look for cards which require the agpgart module */
    agpgartInitialize(modLoaded, modDeps, modInfo, flags);

    mlLoadModuleSetLocation("raid0:raid1:raid5:msdos:ext3:reiserfs:jfs:xfs:lvm-mod",
			    modLoaded, modDeps, modInfo, flags, 
			    secondStageModuleLocation);

    initializeParallelPort(modLoaded, modDeps, modInfo, flags);

    usbInitializeMouse(modLoaded, modDeps, modInfo, flags);

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
        startNewt(flags);
        
        /* JKFIXME: this seems broken... we should just ask these questions
         * earlier for rescue mode and do the fast path check later */
#if 0
        if (!lang) {
            int rc;
            
            do {
                chooseLanguage(&lang, flags);
                defaultLang = 0;
                rc = chooseKeyboard (&keymap, &kbdtype, flags);
            } while ((rc) && (rc != LOADER_NOOP));
        }
#endif
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
            *argptr++ = ksFile;
        }

        /* JKFIXME: obviously this needs to come back... */
#if 0        
        if (!lang)
            lang = getenv ("LC_ALL");
        
        if (lang && !defaultLang && !FL_NOPASS(flags)) {
            *argptr++ = "--lang";
            *argptr++ = lang;
        }
        
        if (keymap && !FL_NOPASS(flags)) {
            *argptr++ = "--keymap";
            *argptr++ = keymap;
        }
        
        if (kbdtype && !FL_NOPASS(flags)) {
            *argptr++ = "--kbdtype";
            *argptr++ = kbdtype;
        }
#endif
        
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
    
    return 1;
}
