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
 *
 * Copyright 1999 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <arpa/inet.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#include "isys/imount.h"
#include "pump/pump.h"
#include "isys/isys.h"
#include "isys/probe.h"
#include "isys/pci/pciprobe.h"

#include "devices.h"
#include "lang.h"
#include "loader.h"
#include "log.h"
#include "modules.h"
#include "net.h"
#include "windows.h"

struct knownDevices devices;

struct installMethod {
    char * name;
    int network;
    int (*mountImage)(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
};

static int mountCdromImage(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
static int mountNfsImage(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);

static struct installMethod installMethods[] = {
    { N_("Local CDROM"), 0, mountCdromImage },
    { N_("NFS image"), 1, mountNfsImage }
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

static int newtRunning = 0;

static void startNewt(void) {
    if (!newtRunning) {
	newtInit();
	newtCls();
	newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));

	newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
	newtRunning = 1;
    }
}

static void stopNewt(void) {
    if (newtRunning) newtFinished();
}

static void spawnShell(int flags) {
    pid_t pid;
    int fd;

    if (!FL_TESTING(flags)) {
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
		perror("could not set new controlling tty");
	    }

	    execl("/bin/sh", "-/bin/sh", NULL);
	    logMessage("exec of /bin/sh failed: %s", strerror(errno));
	}

	close(fd);
    } else {
	logMessage("not spawning a shell as we're in test mode");
    }

    return;
}

static int detectHardware(moduleInfoSet modInfo, 
			  struct moduleInfo *** modules, int flags) {
    struct pciDevice **devices, **device;
    struct moduleInfo * mod, ** modList;
    int numMods, i;

    probePciFreeDrivers();
    if (probePciReadDrivers(FL_TESTING(flags) ? "../isys/pci/pcitable" :
			              "/modules/pcitable")) {
        logMessage("An error occured while reading the PCI ID table");
	return LOADER_ERROR;
    }

    logMessage("looking for devices on pci bus");
    
    devices = probePci(0, 0);
    if (devices == NULL) {
        *modules = NULL;
	return LOADER_OK;
    }

    logMessage("returned from probePci");

    modList = malloc(sizeof(*modList) * 50);	/* should be enough */
    numMods = 0;

    for (device = devices; *device; device++) {
	logMessage("found suggestion of %s", (*device)->driver);
	if ((mod = isysFindModuleInfo(modInfo, (*device)->driver))) {
	    logMessage("found %s device", (*device)->driver);
	    for (i = 0; i < numMods; i++) 
	        if (modList[i] == mod) break;
	    if (i == numMods) 
		modList[numMods++] = mod;
	}
    }

    if (numMods) {
        *modules = modList;
	modList[numMods] = NULL;
    } else {
        free(modList);
	*modules = NULL;
    }

    free(devices);

    return LOADER_OK;
}

int pciProbe(moduleInfoSet modInfo, moduleList modLoaded, moduleDeps modDeps,
	     int justProbe, struct knownDevices * kd, int flags) {
    int i;
    struct moduleInfo ** modList;

    if (!access("/proc/bus/pci/devices", R_OK)) {
        /* autodetect whatever we can */
        if (detectHardware(modInfo, &modList, flags)) {
	    logMessage("failed to scan pci bus!");
	    return 0;
	} else if (modList) {
	    logMessage("found devices justProbe is %d", justProbe);

	    for (i = 0; modList[i]; i++) {
		if (justProbe) {
		    printf("%s\n", modList[i]->moduleName);
		} else {
		    if (modList[i]->major == DRIVER_NET) {
			mlLoadModule(modList[i]->moduleName, modLoaded, 
				     modDeps, FL_TESTING(flags));
		    }
		}
	    }

	    for (i = 0; !justProbe && modList[i]; i++) {
	    	if (modList[i]->major == DRIVER_SCSI) {
		    startNewt();

		    winStatus(40, 3, _("Loading SCSI driver"), 
		    	      "Loading %s driver...", modList[i]->moduleName);
		    mlLoadModule(modList[i]->moduleName, modLoaded, modDeps, 
				 FL_TESTING(flags));
		    newtPopWindow();
		}
	    }

	    kdFindScsiList(kd);
	    kdFindNetList(kd);
	} else 
	    logMessage("found nothing");
    }

    return 0;
}

static int mountCdromImage(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    int i;
    int rc;

    do {
	for (i = 0; i < kd->numKnown; i++) {
	    if (kd->known[i].class != DEVICE_CDROM) continue;

	    logMessage("trying to mount device %s", kd->known[i].name);
	    devMakeInode(kd->known[i].name, "/tmp/cdrom");
	    if (!doPwMount("/tmp/cdrom", "/mnt/source", "iso9660", 1, 0, NULL, 
			  NULL)) {
		if (!access("/mnt/source/RedHat/instimage/usr/bin/anaconda", 
			    X_OK)) 
		    return 0;
		umount("/mnt/source");
	    }
	}

	rc = newtWinChoice(_("Error"), _("Ok"), _("Back"), 
			_("I could not find a Red Hat Linux "
			  "CDROM in any of your CDROM drives. Please insert "
			  "the Red Hat CD and press \"Ok\" to retry."));
	if (rc == 2) break;
    } while (1);

    return LOADER_BACK;
}

static int ensureNetDevice(struct knownDevices * kd,
    		         moduleInfoSet modInfo, moduleList modLoaded,
		         moduleDeps modDeps, int flags, char ** devNamePtr) {
    int i, rc;
    char * devName = NULL;

    /* Once we find an ethernet card, we're done. Perhaps we should
       let them specify multiple ones here?? */

    for (i = 0; i < kd->numKnown; i++) {
	if (kd->known[i].class == DEVICE_NET) {
	    devName = kd->known[i].name;
	    break;
	}
    }

    /* It seems like expert mode should do something here? */
    if (!devName) {
	rc = devDeviceMenu(DRIVER_NET, modInfo, modLoaded, modDeps, flags);
	if (rc) return rc;
	kdFindNetList(kd);
    }

    if (!devName) {
	for (i = 0; i < kd->numKnown; i++) {
	    if (kd->known[i].class == DEVICE_NET) {
		devName = kd->known[i].name;
		break;
	    }
	}
    }

    if (!devName) return LOADER_ERROR;

    *devNamePtr = devName;

    return 0;
}

static int mountNfsImage(char * location, struct knownDevices * kd,
    		         moduleInfoSet modInfo, moduleList modLoaded,
		         moduleDeps modDeps, int flags) {
    struct pumpNetIntf netDev;
    char * devName;
    int i;
    char * host = NULL;
    char * dir = NULL;
    char * fullPath;

    i = ensureNetDevice(kd, modInfo, modLoaded, modDeps, flags, &devName);
    if (i) return i;

    readNetConfig(devName, &netDev, flags);
    nfsGetSetup(&host, &dir);
    
    if (!FL_TESTING(flags)) {
	pumpSetupInterface(&netDev);
	pumpSetupDefaultGateway(&netDev.gateway);

	mlLoadModule("nfs", modLoaded, modDeps, flags);

	fullPath = alloca(strlen(host) + strlen(dir) + 2);
	sprintf(fullPath, "%s:%s", host, dir);

	logMessage("mounting nfs path %s", fullPath);

	doPwMount(fullPath, "/mnt/source", "nfs", 1, 0, NULL, NULL);
    }		  

    free(host);
    free(dir);

    return 0;
}
    
static int doMountImage(char * location, struct knownDevices * kd,
    		        moduleInfoSet modInfo,
			moduleList modLoaded,
		        moduleDeps modDeps, int flags) {
    static int defaultMethod = 0;
    int i, rc;
    int validMethods[10];
    int numValidMethods = 0;
    char * installNames[10];
    int methodNum = 0;
    int networkAvailable = 0;
    void * class;

    if ((class = isysGetModuleList(modInfo, DRIVER_NET))) {
	networkAvailable = 1;
	free(class);
    }

    for (i = 0; i < numMethods; i++) {
	if ((networkAvailable && installMethods[i].network) ||
		(!networkAvailable && !installMethods[i].network)) {
	    if (i == defaultMethod) methodNum = numValidMethods;

	    installNames[numValidMethods] = installMethods[i].name;
	    validMethods[numValidMethods++] = i;
	}
    }

    installNames[numValidMethods] = NULL;

    if (!numValidMethods) {
	logMessage("no install methods have the required devices!\n");
	return LOADER_ERROR;
    }

    do { 
	rc = newtWinMenu(_("Installation Method"), 
			 _("What type of media contains the packages to be "
			   "installed?"), 30, 10, 20, 6, installNames, 
			 &methodNum, _("Ok"), _("Back"), NULL);

	if (rc == 2) return LOADER_BACK;

    	rc = installMethods[validMethods[methodNum]].mountImage(location,
    		   kd, modInfo, modLoaded, modDeps, flags);
    } while (rc == 2);

    return 0;
}

static int parseCmdLineFlags(int flags, char * cmdLine) {
    int fd;
    char buf[500];
    int len;
    char ** argv;
    int argc;
    int i;

    if (!cmdLine) {
	if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return flags;
	len = read(fd, buf, sizeof(buf) - 1);
	close(fd);
	if (len <= 0) return flags;

	buf[len] = '\0';
	cmdLine = buf;
    }

    if (poptParseArgvString(cmdLine, &argc, &argv)) return flags;

    for (i = 0; i < argc; i++) {
        if (!strcasecmp(argv[i], "expert"))
	    flags |= LOADER_FLAGS_EXPERT;
        else if (!strcasecmp(argv[i], "text"))
	    flags |= LOADER_FLAGS_TEXT;
    }

    return flags;
}

int main(int argc, char ** argv) {
    char ** argptr;
    char * anacondaArgs[30];
    char * arg;
    poptContext optCon;
    int probeOnly = 0;
    moduleList modLoaded;
    char * cmdLine = NULL;
    moduleDeps modDeps;
    int i, rc;
    int flags = 0;
    int testing = 0;
    struct knownDevices kd;
    moduleInfoSet modInfo;
    struct poptOption optionTable[] = {
    	    { "cmdline", '\0', POPT_ARG_STRING, &cmdLine, 0,
	    	"override /proc/cmdline contents" },
	    { "probe", '\0', POPT_ARG_NONE, &probeOnly, 0,
	    	"display a list of probed pci devices" },
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
	    POPT_AUTOHELP
	    { 0, 0, 0, 0, 0 }
    };

    optCon = poptGetContext(NULL, argc, argv, optionTable, 0);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	fprintf(stderr, "bad option %s: %s\n",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	exit(1);
    }

    if ((arg = poptGetArg(optCon))) {
	fprintf(stderr, "unexpected argument: %s\n", arg);
	exit(1);
    }

    if (testing) flags |= LOADER_FLAGS_TESTING;

    flags = parseCmdLineFlags(flags, cmdLine);

    arg = FL_TESTING(flags) ? "/boot/module-info" : "/modules/module-info";
    modInfo = isysNewModuleInfoSet();
    if (isysReadModuleInfo(arg, modInfo)) {
        fprintf(stderr, "failed to read %s\n", arg);
	sleep(5);
	exit(1);
    }

    openLog(FL_TESTING(flags));

    kd = kdInit();

    kdFindIdeList(&kd);
    kdFindScsiList(&kd);
    kdFindNetList(&kd);
    mlReadLoadedList(&modLoaded);
    modDeps = mlNewDeps();
    mlLoadDeps(&modDeps, "/modules/modules.dep");

    pciProbe(modInfo, modLoaded, modDeps, probeOnly, &kd, flags);
    if (probeOnly) exit(0);

    startNewt();

    doMountImage("/mnt/source", &kd, modInfo, modLoaded, modDeps, 
		 FL_TESTING(flags));

    if (!FL_TESTING(flags)) {
     
	symlink("mnt/source/RedHat/instimage/usr", "/usr");
	symlink("mnt/source/RedHat/instimage/lib", "/lib");

	unlink("/modules/modules.dep");
	unlink("/modules/module-info");
	unlink("/modules/modules.cgz");
	unlink("/modules/pcitable");

	symlink("../mnt/source/RedHat/instimage/modules/modules.dep",
		"/modules/modules.dep");
	symlink("../mnt/source/RedHat/instimage/modules/module-info",
		"/modules/module-info");
	symlink("../mnt/source/RedHat/instimage/modules/modules.cgz",
		"/modules/modules.cgz");
	symlink("../mnt/source/RedHat/instimage/modules/pcitable",
		"/modules/pcitable");
    }

    spawnShell(flags);			/* we can attach gdb now :-) */

    /* XXX should free old Deps */
    modDeps = mlNewDeps();
    mlLoadDeps(&modDeps, "/modules/modules.dep");

    modInfo = isysNewModuleInfoSet();
    if (isysReadModuleInfo(arg, modInfo)) {
        fprintf(stderr, "failed to read %s\n", arg);
	sleep(5);
	exit(1);
    }
    pciProbe(modInfo, modLoaded, modDeps, 0, &kd, flags);

    if (!FL_TESTING(flags)) {
        int fd;

	fd = open("/tmp/conf.modules", O_WRONLY | O_CREAT, 0666);
	if (fd < 0) {
	    logMessage("error creating /tmp/conf.modules: %s\n", 
	    	       strerror(errno));
	} else {
	    mlWriteConfModules(modLoaded, modInfo, fd);
	    close(fd);
	}
    }

    stopNewt();
    closeLog();

    for (i = 0; i < kd.numKnown; i++) {
    	printf("%-5s ", kd.known[i].name);
	if (kd.known[i].class == DEVICE_CDROM)
	    printf("cdrom");
	else if (kd.known[i].class == DEVICE_DISK)
	    printf("disk ");
	else if (kd.known[i].class == DEVICE_NET)
	    printf("net  ");
    	if (kd.known[i].model)
	    printf(" %s\n", kd.known[i].model);
	else
	    printf("\n");
    }

    argptr = anacondaArgs;
    *argptr++ = "/usr/bin/anaconda";
    *argptr++ = "-p";
    *argptr++ = "/mnt/source";

    if (FL_TEXT(flags))
	*argptr++ = "-T";
    
    if (!FL_TESTING(flags)) {
    	execv(anacondaArgs[0], anacondaArgs);
        perror("exec");
    }

    return 1;
}

