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
#include <zlib.h>

#include "balkan/balkan.h"
#include "isys/imount.h"
#include "isys/isys.h"
#include "isys/probe.h"
#include "isys/pci/pciprobe.h"

#include "cdrom.h"
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
static int mountHardDrive(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
static int mountNfsImage(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);

static struct installMethod installMethods[] = {
    { N_("Local CDROM"), 0, mountCdromImage },
    { N_("Hard drive"), 0, mountHardDrive },
    { N_("NFS image"), 1, mountNfsImage }
};
static int numMethods = sizeof(installMethods) / sizeof(struct installMethod);

static int newtRunning = 0;

void doSuspend(void) {
    newtFinished();
    exit(1);
}

static void startNewt(int flags) {
    if (!newtRunning) {
	newtInit();
	newtCls();
	newtDrawRootText(0, 0, _("Welcome to Red Hat Linux"));

	newtPushHelpLine(_("  <Tab>/<Alt-Tab> between elements  | <Space> selects | <F12> next screen "));
	newtRunning = 1;
        if (FL_TESTING(flags)) 
	    newtSetSuspendCallback((void *) doSuspend, NULL);
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

int addDeviceManually(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps modDeps, struct knownDevices * kd, int flags) {
    char * pristineItems[] = { N_("SCSI"), N_("Network"), NULL };
    char * items[3];
    int i, rc;
    int choice = 0;
    enum deviceClass type;

    for (i = 0; i < 3; i++) {
	items[i] = _(pristineItems[i]);
    }

    do {
	rc = newtWinMenu(_("Devices"), 
		       _("What kind of device would you like to add"), 40,
		       0, 20, 2, items, &choice, _("Ok"), _("Back"), NULL);
	if (rc == 2) return LOADER_BACK;

	if (choice == 1)
	    type = DRIVER_NET;
	else
	    type = DRIVER_SCSI;

	rc = devDeviceMenu(type, modInfo, modLoaded, modDeps, flags, NULL);
    } while (rc);

    return 0;
}

int manualDeviceCheck(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps modDeps, struct knownDevices * kd, int flags) {
    int i, rc;
    char buf[2000];
    struct moduleInfo * mi;
    newtComponent done, add, text, items, form, answer;
    newtGrid grid, buttons;
    int numItems;
    int maxWidth;
    char * t;

    while (1) {
	numItems = 0;
        maxWidth = 0;
	for (i = 0, *buf = '\0'; i < modLoaded->numModules; i++) {
	    if (!modLoaded->mods[i].weLoaded) continue;

	    strcat(buf, "    ");

	    if ((mi = isysFindModuleInfo(modInfo, modLoaded->mods[i].name))) {
		t = mi->description;
	    } else {
		t = modLoaded->mods[i].name;
	    }

	    strcat(buf, t);

	    if (maxWidth < strlen(t)) maxWidth = strlen(t);

	    strcat(buf, "\n");
	    numItems++;
	}

        if (numItems > 0) {
	    text = newtTextboxReflowed(-1, -1, 
		_("I have found the following devices in your system:"), 
		40, 5, 20, 0);
	    buttons = newtButtonBar(_("Done"), &done, _("Add Device"), &add, 
				    NULL);
	    items = newtTextbox(-1, -1, maxWidth + 8, 
				numItems < 10 ? numItems : 10, 
				(numItems < 10 ? 0 : NEWT_FLAG_SCROLL));
				    
	    newtTextboxSetText(items, buf);

	    grid = newtGridSimpleWindow(text, items, buttons);
	    newtGridWrappedWindow(grid, _("Devices"));

	    form = newtForm(NULL, NULL, 0);
	    newtGridAddComponentsToForm(grid, form, 1);

	    answer = newtRunForm(form);
	    newtPopWindow();

	    newtGridFree(grid, 1);
	    newtFormDestroy(form);

	    if (answer != add)
		break;
	    addDeviceManually(modInfo, modLoaded, modDeps, kd, flags);
	} else {
	    rc = newtWinChoice(_("Devices"), _("Done"), _("Add Device"), 
		    _("I don't have any special device drivers loaded for "
		      "your system. Would you like to load some now?"));
	    if (rc != 2)
		break;

	    addDeviceManually(modInfo, modLoaded, modDeps, kd, flags);
	}
    } 


    return 0;
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
				     modDeps, NULL, FL_TESTING(flags));
		    }
		}
	    }

	    for (i = 0; !justProbe && modList[i]; i++) {
	    	if (modList[i]->major == DRIVER_SCSI) {
		    startNewt(flags);

		    winStatus(40, 3, _("Loading SCSI driver"), 
		    	      "Loading %s driver...", modList[i]->moduleName);
		    mlLoadModule(modList[i]->moduleName, modLoaded, modDeps, 
				 NULL, FL_TESTING(flags));
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

static int loadCompressedRamdisk(int fd, off_t size, char *title,
				 char *ramdisk, int flags) {
    int rc = 0, ram, i;
    gzFile stream;
    char buf[1024];
    newtComponent form = NULL, scale = NULL;
    int total;

    if (FL_TESTING(flags)) return 0;

    stream = gzdopen(dup(fd), "r");

    strcpy(buf, "/tmp/");
    strcat(buf, ramdisk);
    
    if (devMakeInode(ramdisk, buf)) return 1;
    ram = open(buf, O_WRONLY);
    unlink(buf);

    logMessage("created inode");

    if (title != NULL) {
	if (size > 0)
	    newtCenteredWindow(70, 5, _("Loading"));
	else
	    newtCenteredWindow(70, 3, _("Loading"));
	
	form = newtForm(NULL, NULL, 0);
	
	newtFormAddComponent(form, newtLabel(1, 1, title));
	if (size > 0) {
	    scale = newtScale(1, 3, 68, size);
	    newtFormAddComponent(form, scale);
	}
	newtDrawForm(form);
	newtRefresh();
    }

    total = 0;
    while (!gzeof(stream) && !rc) {
	if ((i = gzread(stream, buf, sizeof(buf))) != sizeof(buf)) {
	    if (!gzeof(stream)) {
		logMessage("error reading from device: %s", strerror(errno));
		rc = 1;
		break;
	    }
	}

	if (write(ram, buf, i) != i) {
	    logMessage("error writing to device: %s", strerror(errno));
	    rc = 1;
	}

	total += i;

	if (title != NULL && size > 0) {
	    newtScaleSet(scale, lseek(fd, 0L, SEEK_CUR));
	    newtRefresh();
	}
    }

    logMessage("done loading %d bytes", total);

    if (title != NULL) {
	newtPopWindow();
	newtFormDestroy(form);
    }
    
    close(ram);
    gzclose(stream);

    return rc;
}

static int loadStage2Ramdisk(int fd, off_t size, int flags) {
    int rc;
    
    rc = loadCompressedRamdisk(fd, size, _("Loading second stage ramdisk..."),
			       "ram3", flags);
    
    if (rc) {
	newtWinMessage(_("Error"), _("Ok"), _("Error loading ramdisk."));
	return rc;
    }

    if (devMakeInode("ram3", "/tmp/ram3")) return 1;
    
    if (doPwMount("/tmp/ram3", "/mnt/runtime", "ext2", 1, 0, NULL, NULL)) {
logMessage("mount error %s", strerror(errno));
	newtWinMessage(_("Error"), _("Ok"),
		"Error mounting ramdisk. This shouldn't "
		    "happen, and I'm rebooting your system now.");
	exit(1);
    }

    unlink("/tmp/ram3");

    return 0;
}

static int mountHardDrive(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    int rc;
    int fd;
    int i, j;
    struct {
	char name[20];
	int type;
    } partitions[1024], * part;
    int numPartitions = 0;
    struct partitionTable table;
    newtComponent listbox, label, dirEntry, form, answer, okay, back, text;
    newtGrid entryGrid, grid, buttons;
    int done = 0;
    char * dir = NULL;
    char * type;
    char * path;

    /* XXX load scsi devices here */


    /*mlLoadModule("vfat", modLoaded, modDeps, NULL, flags);*/

    for (i = 0; i < kd->numKnown; i++) {
	if (kd->known[i].class == DEVICE_DISK) {
	    devMakeInode(kd->known[i].name, "/tmp/hddevice");
	    if ((fd = open("/tmp/hddevice", O_RDONLY)) >= 0) {
		if ((rc = balkanReadTable(fd, &table))) {
		    logMessage("failed to read partition table for "
			       "device %s: %d", kd->known[i].name, rc);
		} else {
		    for (j = 0; j < table.maxNumPartitions; j++) {
			if (table.parts[j].type == BALKAN_PART_DOS ||
				table.parts[j].type == BALKAN_PART_EXT2) {
			    sprintf(partitions[numPartitions].name, 
				    "/dev/%s%d", kd->known[i].name, j + 1);
			    partitions[numPartitions].type = 
				    table.parts[j].type;
			    numPartitions++;
			}
		    }
		}

		close(fd);
	    } else {
		/* XXX ignore errors on removable drives? */
	    }

	    unlink("/tmp/hddevice");
	}
    }

    if (!numPartitions) {
	newtWinMessage(_("Error"), _("Ok"), 
			_("You don't seem to have any hard drives on "
			  "your system!"));
	return LOADER_BACK;
    }

    while (!done) {
	text = newtTextboxReflowed(-1, -1,
		_("What partition and directory on that partition hold the "
		  "RedHat/RPMS and RedHat/base directories?"), 62, 5, 5, 0);

	listbox = newtListbox(-1, -1, numPartitions > 5 ? 5 : numPartitions,
			      numPartitions > 5 ? NEWT_FLAG_SCROLL : 0);
	
	for (i = 0; i < numPartitions; i++) 
	    newtListboxAppendEntry(listbox, partitions[i].name, 
				   partitions + i);
	
	label = newtLabel(-1, -1, _("Directory holding Red Hat:"));
	dirEntry = newtEntry(28, 11, dir, 28, &dir, NEWT_ENTRY_SCROLL);
	
	entryGrid = newtGridHStacked(NEWT_GRID_COMPONENT, label,
				     NEWT_GRID_COMPONENT, dirEntry,
				     NEWT_GRID_EMPTY);

	buttons = newtButtonBar(_("Ok"), &okay, _("Back"), &back, NULL);
	
	grid = newtCreateGrid(1, 4);
	newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
			 0, 0, 0, 1, 0, 0);
	newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, listbox,
			 0, 0, 0, 1, 0, 0);
	newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, entryGrid,
			 0, 0, 0, 1, 0, 0);
	newtGridSetField(grid, 0, 3, NEWT_GRID_SUBGRID, buttons,
			 0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);
	
	newtGridWrappedWindow(grid, _("Select Partition"));
	
	form = newtForm(NULL, NULL, 0);
	newtGridAddComponentsToForm(grid, form, 1);
	newtGridFree(grid, 1);
	
	answer = newtRunForm(form);
	part = newtListboxGetCurrent(listbox);

	if (dir && *dir)
	    dir = strdup(dir);
	else
	    dir = NULL;
	
	newtFormDestroy(form);
	newtPopWindow();
	
	if (answer == back) return LOADER_BACK;

	logMessage("partition %s selected", part->name);
	
	switch (part->type) {
	  case BALKAN_PART_EXT2:    type = "ext2"; 		break;
	  case BALKAN_PART_DOS:	    type = "vfat"; 		break;
	  default:	continue;
	}

	if (!FL_TESTING(flags)) {
	    logMessage("mounting device %s as %s", part->name, type);

	    /* +5 skips over /dev/ */
	    if (devMakeInode(part->name + 5, "/tmp/hddev"))
		logMessage("devMakeInode failed!");

	    if (doPwMount("/tmp/hddev", "/tmp/hdimage", type, 1, 0, NULL, NULL))
		continue;

	    logMessage("opening stage2");

	    path = malloc(50 + (dir ? strlen(dir) : 2));
	    sprintf(path, "/tmp/hdimage/%s/RedHat/base/stage2.img", 
			dir ? dir : "");
	    if (dir) free(dir);
	    if ((fd = open(path, O_RDONLY)) < 0) {
		logMessage("cannot open %s", path);
		newtWinMessage(_("Error"), _("Ok"), 
			    _("Device %s does not appear to contain "
			      "a Red Hat installation tree."), part->name);
		umount("/tmp/hdimage");
		free(path);
		continue;
	    } 

	    free(path);

	    rc = loadStage2Ramdisk(fd, 0, flags);
	    close(fd);
	    if (rc) continue;
	}

	done = 1; 

	umount("/tmp/hdimage");
	rmdir("/tmp/hdimage");
    }

    return 0;
}

static int mountCdromImage(char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    int i;
    int rc;
    int hasCdrom = 0;

    do {
	for (i = 0; i < kd->numKnown; i++) {
	    if (kd->known[i].class != DEVICE_CDROM) continue;

	    hasCdrom = 1;

	    logMessage("trying to mount device %s", kd->known[i].name);
	    devMakeInode(kd->known[i].name, "/tmp/cdrom");
	    if (!doPwMount("/tmp/cdrom", "/mnt/source", "iso9660", 1, 0, NULL, 
			  NULL)) {
		if (!access("/mnt/source/RedHat/instimage/usr/bin/anaconda", 
			    X_OK)) {
		    symlink("/mnt/source/RedHat/instimage", "/mnt/runtime");
		    return 0;
		}
		umount("/mnt/source");
	    }
	}

	if (hasCdrom) {
	    rc = newtWinChoice(_("Error"), _("Ok"), _("Back"), 
			_("I could not find a Red Hat Linux "
			  "CDROM in any of your CDROM drives. Please insert "
			  "the Red Hat CD and press \"Ok\" to retry."));
	    if (rc == LOADER_BACK) break;
	} else {
	    rc = setupCDdevice(kd, modInfo, modLoaded, modDeps, flags);
	    if (rc == LOADER_BACK) break;
	}
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
	rc = devDeviceMenu(DRIVER_NET, modInfo, modLoaded, modDeps, flags,
			   NULL);
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

#define NFS_STAGE_IP	1
#define NFS_STAGE_NFS	2
#define NFS_STAGE_MOUNT	3
#define NFS_STAGE_DONE	4

static int mountNfsImage(char * location, struct knownDevices * kd,
    		         moduleInfoSet modInfo, moduleList modLoaded,
		         moduleDeps modDeps, int flags) {
    static struct networkDeviceConfig netDev;
    char * devName;
    int i, rc;
    char * host = NULL;
    char * dir = NULL;
    char * fullPath;
    int stage = NFS_STAGE_IP;

    i = ensureNetDevice(kd, modInfo, modLoaded, modDeps, flags, &devName);
    if (i) return i;

    while (stage != NFS_STAGE_DONE) {
        switch (stage) {
	  case NFS_STAGE_IP:
	    rc = readNetConfig(devName, &netDev, flags);
	    if (rc) {
		pumpDisableInterface(devName);
		return rc;
	    }
	    stage = NFS_STAGE_NFS;
	    break;

	  case NFS_STAGE_NFS:
	    if (nfsGetSetup(&host, &dir) == LOADER_BACK)
		stage = NFS_STAGE_IP;
	    else
		stage = NFS_STAGE_MOUNT;
	    break;

	  case NFS_STAGE_MOUNT:
	    if (FL_TESTING(flags)) {
		stage = NFS_STAGE_DONE;
		break;
	    }

	    mlLoadModule("nfs", modLoaded, modDeps, NULL, flags);
	    fullPath = alloca(strlen(host) + strlen(dir) + 2);
	    sprintf(fullPath, "%s:%s", host, dir);

	    logMessage("mounting nfs path %s", fullPath);

	    stage = NFS_STAGE_NFS;

	    if (!doPwMount(fullPath, "/mnt/source", "nfs", 1, 0, NULL, NULL)) {
		if (!access("/mnt/source/RedHat/instimage/usr/bin/anaconda", 
			    X_OK)) {
		    symlink("/mnt/source/RedHat/instimage", "/mnt/runtime");
		    stage = NFS_STAGE_DONE;
		} else {
		    umount("/mnt/source");
		    newtWinMessage(_("Error"), _("Ok"), 
				   _("That directory does not seem to contain "
				     "a Red Hat installation tree."));
		}
	    } else {
		newtWinMessage(_("Error"), _("Ok"), 
		        _("I could not mount that directory from the server"));
	    }

	    break;
        }
    }

    writeNetInfo("/tmp/netinfo", &netDev);

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
    int localAvailable = 0;
    void * class;

    if ((class = isysGetModuleList(modInfo, DRIVER_NET))) {
	networkAvailable = 1;
	free(class);
    }

    if ((class = isysGetModuleList(modInfo, DRIVER_SCSI))) {
	localAvailable = 1;
	free(class);
    }

    for (i = 0; i < numMethods; i++) {
	if ((networkAvailable && installMethods[i].network) ||
		(localAvailable && !installMethods[i].network)) {
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
			 &methodNum, _("Ok"), NULL);

    	rc = installMethods[validMethods[methodNum]].mountImage(location,
    		   kd, modInfo, modLoaded, modDeps, flags);
    } while (rc);

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

    arg = FL_TESTING(flags) ? "./module-info" : "/modules/module-info";
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

    startNewt(flags);

    doMountImage("/mnt/source", &kd, modInfo, modLoaded, modDeps, 
		 FL_TESTING(flags));

    if (!FL_TESTING(flags)) {
     
	symlink("mnt/runtime/usr", "/usr");
	symlink("mnt/runtime/lib", "/lib");

	unlink("/modules/modules.dep");
	unlink("/modules/module-info");
	unlink("/modules/modules.cgz");
	unlink("/modules/pcitable");

	symlink("../mnt/runtime/modules/modules.dep",
		"/modules/modules.dep");
	symlink("../mnt/runtime/modules/module-info",
		"/modules/module-info");
	symlink("../mnt/runtime/modules/modules.cgz",
		"/modules/modules.cgz");
	symlink("../mnt/runtime/modules/pcitable",
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

    if (access("/proc/pci", X_OK) || FL_EXPERT(flags)) {
	manualDeviceCheck(modInfo, modLoaded, modDeps, &kd, flags);
    }

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

