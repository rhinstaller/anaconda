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
#include <rpmio.h>
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
#include "kickstart.h"
#include "lang.h"
#include "loader.h"
#include "log.h"
#include "modules.h"
#include "net.h"
#include "pcmcia.h"
#include "urls.h"
#include "windows.h"

int probe_main(int argc, char ** argv);
int rmmod_main(int argc, char ** argv);
int cardmgr_main(int argc, char ** argv);
int ourInsmodCommand(int argc, char ** argv);

struct knownDevices devices;

struct installMethod {
    char * name;
    int network;
    enum deviceClass deviceType;			/* for pcmcia */
    char * (*mountImage)(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
};

static char * mountCdromImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
static char * mountHardDrive(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
static char * mountNfsImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);
static char * mountUrlImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags);

static struct installMethod installMethods[] = {
    { N_("Local CDROM"), 0, DEVICE_CDROM, mountCdromImage },
    { N_("NFS image"), 1, DEVICE_NET, mountNfsImage },
    { "FTP", 1, DEVICE_NET, mountUrlImage },
    { "HTTP", 1, DEVICE_NET, mountUrlImage },
    { N_("Hard drive"), 0, DEVICE_DISK, mountHardDrive },
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

    while (1) {
	numItems = 0;
        maxWidth = 0;
	for (i = 0, *buf = '\0'; i < modLoaded->numModules; i++) {
	    if (!modLoaded->mods[i].weLoaded) continue;

	    if (!(mi = isysFindModuleInfo(modInfo, modLoaded->mods[i].name))) {
		continue;
	    }

	    strcat(buf, "    ");
	    strcat(buf, mi->description);

	    if (maxWidth < strlen(mi->description)) 
		maxWidth = strlen(mi->description);

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
				     modDeps, NULL, flags);
		    }
		}
	    }

	    for (i = 0; !justProbe && modList[i]; i++) {
	    	if (modList[i]->major == DRIVER_SCSI) {
		    startNewt(flags);

		    scsiWindow(modList[i]->moduleName);
		    mlLoadModule(modList[i]->moduleName, modLoaded, modDeps, 
				 NULL, flags);
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
    
    if (doPwMount("/tmp/ram3", "/mnt/runtime", "ext2", 0, 0, NULL, NULL)) {
	newtWinMessage(_("Error"), _("Ok"),
		"Error mounting ramdisk. This shouldn't "
		    "happen, and I'm rebooting your system now.");
	exit(1);
    }

    unlink("/tmp/ram3");

    return 0;
}

static char * setupHardDrive(char * device, char * type, char * dir, 
			     int flags) {
    int fd;
    char * path;
    int rc;
    char * url;

    logMessage("mounting device %s as %s", device, type);

    if (!FL_TESTING(flags)) {
	/* +5 skips over /dev/ */
	if (devMakeInode(device, "/tmp/hddev"))
	    logMessage("devMakeInode failed!");

	if (doPwMount("/tmp/hddev", "/tmp/hdimage", type, 1, 0, NULL, NULL))
	    return NULL;

	path = alloca(50 + (dir ? strlen(dir) : 2));
	sprintf(path, "/tmp/hdimage/%s/RedHat/base/stage2.img", 
		    dir ? dir : "");
	if ((fd = open(path, O_RDONLY)) < 0) {
	    logMessage("cannot open %s", path);
	    umount("/tmp/hdimage");
	    free(path);
	    return NULL;
	} 

	rc = loadStage2Ramdisk(fd, 0, flags);
	close(fd);
	if (rc) return NULL;
    }

    url = malloc(50 + strlen(dir ? dir : ""));
    sprintf(url, "hd://%s/%s", device + 5, dir ? dir : ".");

    return url;
}

static char * mountHardDrive(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    int rc;
    int fd;
    int i, j;
    struct {
	char name[20];
	int type;
    } partitions[1024], * part;
    struct partitionTable table;
    newtComponent listbox, label, dirEntry, form, okay, back, text;
    struct newtExitStruct es;
    newtGrid entryGrid, grid, buttons;
    int done = 0;
    char * dir = NULL;
    char * tmpDir;
    char * type;
    char * url = NULL;
    int numPartitions;

    mlLoadModule("vfat", modLoaded, modDeps, NULL, flags);

    while (!done) {
	numPartitions = 0;
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
	    rc = newtWinChoice(_("Hard Drives"), _("Yes"), _("Back"),
			    _("You don't seem to have any hard drives on "
			      "your system! Would you like to configure "
			      "additional devices?"));
	    if (rc == 2) return NULL;

	    devDeviceMenu(DRIVER_SCSI, modInfo, modLoaded, modDeps, flags, 
			  NULL);
	    kdFindScsiList(kd);

	    continue;
	}

	text = newtTextboxReflowed(-1, -1,
		_("What partition and directory on that partition hold the "
		  "RedHat/RPMS and RedHat/base directories? If you don't "
		  "see the disk drive you're using listed here, press F2 "
		  "to configure additional devices."), 62, 5, 5, 0);

	listbox = newtListbox(-1, -1, numPartitions > 5 ? 5 : numPartitions,
			      NEWT_FLAG_RETURNEXIT | 
				(numPartitions > 5 ? NEWT_FLAG_SCROLL : 0)
			    );
	
	for (i = 0; i < numPartitions; i++) 
	    newtListboxAppendEntry(listbox, partitions[i].name, 
				   partitions + i);
	
	label = newtLabel(-1, -1, _("Directory holding Red Hat:"));

	tmpDir = dir ? strdup(dir) : NULL;

	dirEntry = newtEntry(28, 11, dir, 28, &tmpDir, NEWT_ENTRY_SCROLL);
	
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
	
	form = newtForm(NULL, NULL, NEWT_FLAG_NOF12);
	newtFormAddHotKey(form, NEWT_KEY_F2);

	newtGridAddComponentsToForm(grid, form, 1);
	newtGridFree(grid, 1);

	newtFormRun(form, &es);

	part = newtListboxGetCurrent(listbox);
	
	if (dir) free(dir);
	if (tmpDir && *tmpDir) {
	    dir = strdup(tmpDir);
	    free(tmpDir);
	} else  {
	    dir = NULL;
	}
	
	newtFormDestroy(form);
	newtPopWindow();

	if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
	    return NULL;
	} else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
	    devDeviceMenu(DRIVER_SCSI, modInfo, modLoaded, modDeps, flags, 
			  NULL);
	    kdFindScsiList(kd);
	    continue;
	}

	logMessage("partition %s selected", part->name);
	
	switch (part->type) {
	  case BALKAN_PART_EXT2:    type = "ext2"; 		break;
	  case BALKAN_PART_DOS:	    type = "vfat"; 		break;
	  default:	continue;
	}

	url = setupHardDrive(part->name + 5, type, dir, flags);
	if (dir) free(dir);
	if (url) {
	    newtWinMessage(_("Error"), _("Ok"), 
			_("Device %s does not appear to contain "
			  "a Red Hat installation tree."), part->name);
	    continue;
	}

	done = 1; 

	umount("/tmp/hdimage");
	rmdir("/tmp/hdimage");
    }

    return url;
}

static char * setupCdrom(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags, int probeQuickly) {
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
		    return "dir://mnt/source/.";
		}
		umount("/mnt/source");
	    }
	}

	if (probeQuickly) return NULL;

	if (hasCdrom) {
	    rc = newtWinChoice(_("Error"), _("Ok"), _("Back"), 
			_("I could not find a Red Hat Linux "
			  "CDROM in any of your CDROM drives. Please insert "
			  "the Red Hat CD and press \"Ok\" to retry."));
	    if (rc == 2) return NULL;
	} else {
	    rc = setupCDdevice(kd, modInfo, modLoaded, modDeps, flags);
	    if (rc == 2) return NULL;
	}
    } while (1);

    return "dir://mnt/source/.";
}

static char * mountCdromImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    return setupCdrom(method, location, kd, modInfo, modLoaded, modDeps,
		      flags, 0);
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

static char * mountNfsImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		         moduleInfoSet modInfo, moduleList modLoaded,
		         moduleDeps modDeps, int flags) {
    static struct networkDeviceConfig netDev;
    char * devName;
    int i, rc;
    char * host = NULL;
    char * dir = NULL;
    char * fullPath;
    int stage = NFS_STAGE_IP;

    initLoopback();

    memset(&netDev, 0, sizeof(netDev));

    i = ensureNetDevice(kd, modInfo, modLoaded, modDeps, flags, &devName);
    if (i) return NULL;

    while (stage != NFS_STAGE_DONE) {
        switch (stage) {
	  case NFS_STAGE_IP:
	    rc = readNetConfig(devName, &netDev, flags);
	    if (rc) {
		if (!FL_TESTING(flags)) pumpDisableInterface(devName);
		return NULL;
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

    return "dir://mnt/source/.";
}

#define URL_STAGE_IP			1
#define URL_STAGE_MAIN			2
#define URL_STAGE_SECOND		3
#define URL_STAGE_FETCH			4
#define URL_STAGE_DONE			20

static char * mountUrlImage(struct installMethod * method,
		      char * location, struct knownDevices * kd,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags) {
    int i, rc;
    int stage = URL_STAGE_IP;
    char * devName;
    struct iurlinfo ui;
    char needsSecondary = ' ';
    static struct networkDeviceConfig netDev;
    FD_t fd;
    char * url;
    char buf[1024];
    enum urlprotocol_t proto = 
	!strcmp(method->name, "FTP") ? URL_METHOD_FTP : URL_METHOD_HTTP;

    initLoopback();

    i = ensureNetDevice(kd, modInfo, modLoaded, modDeps, flags, &devName);
    if (i) return NULL;

    memset(&ui, 0, sizeof(ui));
    memset(&netDev, 0, sizeof(netDev));

    while (stage != URL_STAGE_DONE) {
        switch (stage) {
	  case URL_STAGE_IP:
	    rc = readNetConfig(devName, &netDev, flags);
	    if (rc) {
		if (!FL_TESTING(flags)) pumpDisableInterface(devName);
		return NULL;
	    }
	    stage = NFS_STAGE_NFS;

	  case URL_STAGE_MAIN:
	    rc = urlMainSetupPanel(&ui, proto, &needsSecondary);
	    if (rc) 
		stage = URL_STAGE_IP;
	    else
		stage = needsSecondary != ' ' ? 
			URL_STAGE_SECOND : URL_STAGE_FETCH;
	    break;

	  case URL_STAGE_SECOND:
	    rc = urlSecondarySetupPanel(&ui, proto);
	    stage = rc ? URL_STAGE_MAIN : URL_STAGE_FETCH;
	    break;

	  case URL_STAGE_FETCH:
	    if (FL_TESTING(flags)) {
		stage = URL_STAGE_DONE;
		break;
	    }

	    fd = urlinstStartTransfer(&ui, "base/stage2.img");
	    
	    if (fd == NULL || fdFileno(fd) < 0) {
		newtPopWindow();
		snprintf(buf, sizeof(buf), "%s/RedHat/base/stage2.img",
			 ui.urlprefix);
		newtWinMessage(_("FTP"), _("Ok"), 
		       _("Unable to retrieve the second stage ramdisk"));
		/*XXX ufdClose(fd);*/
		stage = URL_STAGE_MAIN;
		break;
	    }
	    
	    rc = loadStage2Ramdisk(fdFileno(fd), 0, flags);
	    urlinstFinishTransfer(fd);
	    if (!rc)
		stage = URL_STAGE_DONE;

	    break;
        }
    }

    url = malloc(strlen(ui.urlprefix) + 2);
    strcpy(url, ui.urlprefix);

    writeNetInfo("/tmp/netinfo", &netDev);

    return url;
}
    
static char * doMountImage(char * location, struct knownDevices * kd,
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
    char * url = NULL;

    if ((class = isysGetModuleList(modInfo, DRIVER_NET))) {
	networkAvailable = 1;
	free(class);
    }

    if ((class = isysGetModuleList(modInfo, DRIVER_SCSI))) {
	localAvailable = 1;
	free(class);
    }

#ifdef INCLUDE_PCMCIA
    for (i = 0; i < numMethods; i++) {
	int j;

	for (j = 0; j < kd->numKnown; j++)
	    if (installMethods[i].deviceType == kd->known[j].class) break;

	if (j < kd->numKnown) {
	    if (i == defaultMethod) methodNum = numValidMethods;

	    installNames[numValidMethods] = installMethods[i].name;
	    validMethods[numValidMethods++] = i;
	}
    }
#else
    for (i = 0; i < numMethods; i++) {
	if ((networkAvailable && installMethods[i].network) ||
		(localAvailable && !installMethods[i].network)) {
	    if (i == defaultMethod) methodNum = numValidMethods;

	    installNames[numValidMethods] = installMethods[i].name;
	    validMethods[numValidMethods++] = i;
	}
    }
#endif

    installNames[numValidMethods] = NULL;

    if (!numValidMethods) {
	logMessage("no install methods have the required devices!\n");
	exit(1);
    }

    /* If no network is available, check any attached CDROM device for a
       Red Hat CD. If there is one there, just die happy */
    if (!networkAvailable && !FL_EXPERT(flags)) {
	url = setupCdrom(NULL, location, kd, modInfo, modLoaded, modDeps,
			 flags, 1);
	if (url) return url;
    }

    startNewt(flags);

    do { 
	rc = newtWinMenu(FL_RESCUE(flags) ? _("Rescue Method") :
				_("Installation Method"), 
			 FL_RESCUE(flags) ?
			   _("What type of media contains the rescue image?")
			 :
			   _("What type of media contains the packages to be "
			     "installed?"), 
			 30, 10, 20, 6, installNames, 
			 &methodNum, _("Ok"), NULL);

	if (rc) continue;

    	url = installMethods[validMethods[methodNum]].mountImage(
		   installMethods + validMethods[methodNum], location,
    		   kd, modInfo, modLoaded, modDeps, flags);
    } while (!url);

    return url;
}

static char * setupKickstart(char * location, struct knownDevices * kd,
    		             moduleInfoSet modInfo,
			     moduleList modLoaded,
		             moduleDeps modDeps, int flags) {
    static struct networkDeviceConfig netDev;
    char * host = NULL, * dir = NULL, * partname = NULL;
    char * url = NULL, * proxy = NULL, * proxyport = NULL;
    char ** ksArgv;
    char * fullPath;
    char * device;
    int ksArgc;
    int ksType;
    int i, rc, fd, partNum;
    enum deviceClass ksDeviceType;
    struct poptOption * table;
    poptContext optCon;
    struct partitionTable partTable;
    struct poptOption ksNfsOptions[] = {
	    { "server", '\0', POPT_ARG_STRING, &host, 0 },
	    { "dir", '\0', POPT_ARG_STRING, &dir, 0 },
	    { 0, 0, 0, 0, 0 }
	};
    struct poptOption ksHDOptions[] = {
	    { "dir", '\0', POPT_ARG_STRING, &dir, 0 },
	    { "partition", '\0', POPT_ARG_STRING, &partname, 0 },
	    { 0, 0, 0, 0, 0 }
    };
    struct poptOption ksUrlOptions[] = {
	    { "url", '\0', POPT_ARG_STRING, &url, 0 },
	    { "proxy", '\0', POPT_ARG_STRING, &proxy, 0 },
	    { "proxyport", '\0', POPT_ARG_STRING, &proxyport, 0 },
	    { 0, 0, 0, 0, 0 }
	};

    /* XXX kickstartDevices(modInfo, modLoaded, modDeps); */

    if (ksHasCommand(KS_CMD_NFS)) {
	ksDeviceType = DEVICE_NET;
	ksType = KS_CMD_NFS;
	table = ksNfsOptions;
    } else if (ksHasCommand(KS_CMD_CDROM)) {
	ksDeviceType = DEVICE_CDROM;
	ksType = KS_CMD_CDROM;
	table = NULL;
    } else if (ksHasCommand(KS_CMD_HD)) {
	ksDeviceType = DEVICE_DISK;
	ksType = KS_CMD_HD;
	table = ksHDOptions;
    } else if (ksHasCommand(KS_CMD_URL)) {
	ksDeviceType = DEVICE_NET;
	ksType = KS_CMD_URL;
	table = ksUrlOptions;
    } else {
	logMessage("no install method specified for kickstart");
	return NULL;
    }

    for (i = 0; i < kd->numKnown; i++)
	if (kd->known[i].class == ksDeviceType) break;

    if (i == kd->numKnown) {
	logMessage("no appropriate device for kickstart method is available");
	return NULL;
    }

    device = kd->known[i].name;
    logMessage("kickstarting through device %s", device);

    if (!ksGetCommand(KS_CMD_XDISPLAY, NULL, &ksArgc, &ksArgv)) {
	setenv("DISPLAY", ksArgv[1], 1);
    }

    if (table) {
	ksGetCommand(ksType, NULL, &ksArgc, &ksArgv);

	optCon = poptGetContext(NULL, ksArgc, ksArgv, table, 0);

	if ((rc = poptGetNextOpt(optCon)) < -1) {
	    logMessage("bad argument to kickstart method command %s: %s",
		       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		       poptStrerror(rc));
	    return NULL;
	}
    }

    if (ksType == KS_CMD_NFS || ksType == KS_CMD_URL) {
	startNewt(flags);
	if (kickstartNetwork(device, &netDev, flags)) return NULL;
	writeNetInfo("/tmp/netinfo", &netDev);
    }

    if (ksType == KS_CMD_NFS) {
	mlLoadModule("nfs", modLoaded, modDeps, NULL, flags);
	fullPath = alloca(strlen(host) + strlen(dir) + 2);
	sprintf(fullPath, "%s:%s", host, dir);

	logMessage("mounting nfs path %s", fullPath);

	if (doPwMount(fullPath, "/mnt/source", "nfs", 1, 0, NULL, NULL)) 
	    return NULL;
	    
	symlink("/mnt/source/RedHat/instimage", "/mnt/runtime");

	return "dir://mnt/source/.";
    } else if (ksType == KS_CMD_CDROM) {
	return setupCdrom(NULL, location, kd, modInfo, modLoaded, modDeps, 
			  flags, 1);
    } else if (ksType == KS_CMD_HD) {
	for (i = 0; i < kd->numKnown; i++) {
	    if (kd->known[i].class != DEVICE_DISK) continue;
	    if (!strncmp(kd->known[i].name, partname, strlen(partname) - 1))
		break;
	}
	if (i == kd->numKnown) {
	    logMessage("unknown partition %s", partname);
	    return NULL;
	}

	devMakeInode(kd->known[i].name, "/tmp/hddevice");
	if ((fd = open("/tmp/hddevice", O_RDONLY)) < 0) {
	    logMessage("failed to open device %s", kd->known[i].name);
	    return NULL;
	}

	if ((rc = balkanReadTable(fd, &partTable))) {
	    logMessage("failed to read partition partTable for "
		       "device %s: %d", kd->known[i].name, rc);
	    return NULL;
	}

	partNum = atoi(partname + 3);
	if (partTable.maxNumPartitions < partNum ||
	    partTable.parts[partNum].type == -1) {
	    logMessage("partition %d on device %s does not exist");
	    return NULL;
	}

	/* XXX this shouldn't be hard coded to ext2 */
	return setupHardDrive(partname, 
		partTable.parts[partNum].type == BALKAN_PART_EXT2 ? 
			"ext2" : "vfat", 
	        dir, flags);
    } else if (ksType == KS_CMD_URL) {
	abort();
    }

    return NULL;
}

static int parseCmdLineFlags(int flags, char * cmdLine) {
    int fd;
    char buf[500];
    int len;
    char ** argv;
    int argc;
    int i;

    logMessage("here with cmdLine %s", cmdLine);

    if (!cmdLine) {
	if ((fd = open("/proc/cmdline", O_RDONLY)) < 0) return flags;
	len = read(fd, buf, sizeof(buf) - 1);
	close(fd);
	if (len <= 0) return flags;

	buf[len] = '\0';
	cmdLine = buf;
    }

    logMessage("cmdLine %s", cmdLine);

    if (poptParseArgvString(cmdLine, &argc, &argv)) return flags;

    logMessage("here I am");

    for (i = 0; i < argc; i++) {
        if (!strcasecmp(argv[i], "expert"))
	    flags |= LOADER_FLAGS_EXPERT;
        else if (!strcasecmp(argv[i], "text"))
	    flags |= LOADER_FLAGS_TEXT;
        else if (!strcasecmp(argv[i], "rescue"))
	    flags |= LOADER_FLAGS_RESCUE;
        else if (!strcasecmp(argv[i], "ks=floppy")) {
	    flags |= LOADER_FLAGS_KSFLOPPY;
	    logMessage("got ks=floppy");
	}
    }

    return flags;
}

struct moduleDependency_s {
    char * name;
    char ** deps;
};

int kickstartFromFloppy(char * location, moduleList modLoaded,
			moduleDeps modDeps, int flags) {
    int infd = -1, outfd = -1;
    char buf[4096];
    int i;

    mlLoadModule("vfat", modLoaded, modDeps, NULL, flags);
    if (devMakeInode("fd0", "/tmp/fd0"))
	return 1;

    if (doPwMount("/tmp/fd0", "/tmp/ks", "vfat", 1, 0, NULL, NULL)) {
	logMessage("failed to mount floppy: %s", strerror(errno));
	return 1;
    }

    if (access("/tmp/ks/ks.cfg", R_OK)) {
	newtWinMessage(_("Error"), _("Ok"), 
		_("Cannot find ks.cfg on boot floppy."));
	return 1;
    }


    outfd = open(location, O_CREAT | O_RDWR, 0666);
    infd = open("/tmp/ks/ks.cfg", O_RDONLY);

    while ((i = read(infd, buf, sizeof(buf))) > 0) {
	if (write(outfd, buf, i) != i) break;
    }

    close(infd);
    close(outfd);

    umount("/tmp/ks");
    unlink("/tmp/fd0");

    logMessage("kickstart file copied to %s", location);

    return 0;
}

int main(int argc, char ** argv) {
    char ** argptr;
    char * anacondaArgs[30];
    char * arg, * url;
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
    char * ksFile = NULL;
    struct poptOption optionTable[] = {
    	    { "cmdline", '\0', POPT_ARG_STRING, &cmdLine, 0 },
	    { "ksfile", '\0', POPT_ARG_STRING, &ksFile, 0 },
	    { "probe", '\0', POPT_ARG_NONE, &probeOnly, 0 },
	    { "test", '\0', POPT_ARG_NONE, &testing, 0 },
	    { 0, 0, 0, 0, 0 }
    };

    if (!strcmp(argv[0] + strlen(argv[0]) - 6, "insmod"))
	return ourInsmodCommand(argc, argv);
    else if (!strcmp(argv[0] + strlen(argv[0]) - 5, "rmmod"))
	return rmmod_main(argc, argv);
    else if (!strcmp(argv[0] + strlen(argv[0]) - 8, "modprobe")) {
	return ourInsmodCommand(argc, argv);
    }

#ifdef INCLUDE_PCMCIA
    if (!strcmp(argv[0] + strlen(argv[0]) - 7, "cardmgr"))
	return cardmgr_main(argc, argv);
    else if (!strcmp(argv[0] + strlen(argv[0]) - 5, "probe"))
	return probe_main(argc, argv);
#endif

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
    mlReadLoadedList(&modLoaded);
    modDeps = mlNewDeps();
    mlLoadDeps(&modDeps, "/modules/modules.dep");

logMessage("Flags are 0x%x\n", flags);

    if (FL_KSFLOPPY(flags)) {
	ksFile = "/tmp/ks.cfg";
	kickstartFromFloppy(ksFile, modLoaded, modDeps, flags);
	flags |= LOADER_FLAGS_KICKSTART;
    } else if (FL_KICKSTART(flags)) {
	/* XXX we need to get our ks file from the network */
    }


#ifdef INCLUDE_PCMCIA
    startNewt(flags);

    winStatus(40, 3, _("PC Card"), _("Initializing PC Card Devices..."));
    startPcmcia(modLoaded, modDeps, flags);
    newtPopWindow();
#endif

    kdFindIdeList(&kd);
    kdFindScsiList(&kd);
    kdFindNetList(&kd);

    pciProbe(modInfo, modLoaded, modDeps, probeOnly, &kd, flags);
    if (probeOnly) exit(0);

    if (ksFile) {
	ksReadCommands(ksFile);
	url = setupKickstart("/mnt/source", &kd, modInfo, modLoaded, modDeps, 
			     flags);
    }

    if (!url) {
	url = doMountImage("/mnt/source", &kd, modInfo, modLoaded, modDeps, 
			    flags);
    }

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
    if (FL_RESCUE(flags)) {
	*argptr++ = "/bin/sh";
    } else {
	*argptr++ = "/usr/bin/anaconda";
	*argptr++ = "-m";
	*argptr++ = url;

	if (FL_TEXT(flags))
	    *argptr++ = "-T";
    }

    if (FL_KICKSTART(flags)) {
	*argptr++ = "--kickstart";
	*argptr++ = ksFile;
    }

    *argptr = NULL;
    
    if (!FL_TESTING(flags)) {
    	execv(anacondaArgs[0], anacondaArgs);
        perror("exec");
    }

    return 1;
}

