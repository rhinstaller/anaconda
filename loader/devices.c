#include <alloca.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/utsname.h>
#include <zlib.h>
#include <linux/fd.h>

#include "devices.h"
#include "isys/imount.h"
#include "../isys/isys.h"
#include "lang.h"
#include "loader.h"
#include "log.h"
#include "misc.h"
#include "modules.h"
#include "windows.h"
#include "../kudzu/kudzu.h"
#include "isys/cpio.h"

void eject(char * deviceName) {
    int fd;

#if !defined(__sparc__)
    if (!strncmp(deviceName, "fd", 2)) return;
#endif

    logMessage("ejecting floppy");

    devMakeInode(deviceName, "/tmp/ejectDevice");

    fd = open("/tmp/ejectDevice", O_RDONLY);
    ioctl(fd, FDEJECT, 1);
    close(fd);

    unlink("/tmp/ejectDevice");
}

static int getModuleArgs(struct moduleInfo * mod, char *** argPtr) {
    struct newtWinEntry * entries;
    int i;
    int numArgs;
    char ** values;
    char * chptr, * end;
    int misc = -1;
    char ** args;
    int argc;
    int rc;
    char * text;

    entries = alloca(sizeof(*entries) * (mod->numArgs + 2));
    values = alloca(sizeof(*values) * (mod->numArgs + 2));

    for (i = 0; i < mod->numArgs; i++) {
    	entries[i].text = mod->args[i].description;
	if (mod->args[i].arg) {
	    int io = !strcmp (mod->args[i].arg, "io");
	    values[i] = malloc(strlen(mod->args[i].arg) + (io ? 4 : 2));
	    strcpy(values[i], mod->args[i].arg);
	    strcat(values[i], (io ? "=0x" : "="));
	} else {
	    values[i] = NULL;
	}
	entries[i].value = values + i;
	entries[i].flags = NEWT_FLAG_SCROLL;
    }

    numArgs = i;

    if (!(mod->flags & MI_FLAG_NOMISCARGS)) {
    	values[i] = NULL;
    	entries[i].text = _("Miscellaneous");
    	entries[i].value = values + i;
	entries[i].flags = NEWT_FLAG_SCROLL;
	misc = i;
	i++;
    }

    entries[i].text = (void *) entries[i].value = NULL;

    text = _("This module can take parameters which affects its "
		    "operation. If you don't know what parameters to supply, "
		    "just skip this screen by pressing the \"OK\" button "
		    "now.");

    rc = newtWinEntries(_("Module Parameters"), text,
		        40, 5, 15, 20, entries, _("OK"), 
		        _("Back"), NULL);

    if (rc == 2) {
        for (i = 0; i < numArgs; i++)
	    if (values[i]) free(values[i]);
	return LOADER_BACK;
    }

    /* we keep args big enough for the args we know about, plus a NULL */

    args = malloc(sizeof(*args) * (numArgs + 1));
    argc = 0;

    for (i = 0; i < numArgs; i++) {
    	if (values[i] && *values[i]) {
	    chptr = values[i] + strlen(values[i]) - 1;
	    while (isspace(*chptr)) chptr--;
	    if (*chptr != '=')
		args[argc++] = values[i];
	}
    }

    if (misc >= 0 && values[misc]) {
    	chptr = values[misc];
	i = 1;
	while (*chptr) {
	    if (isspace(*chptr)) i++;
	    chptr++;
	}

	args = realloc(args, sizeof(*args) * (argc + i + 1));
	chptr = values[misc];
	while (*chptr) {
	    while (*chptr && isspace(*chptr)) chptr++;
	    if (!*chptr) break;

	    end = chptr;
	    while (!isspace(*end) && *end) end++;
	    args[argc] = malloc(end - chptr + 1);
	    memcpy(args[argc], chptr, end - chptr);
	    args[argc][end - chptr] = '\0';
	    argc++;
	    chptr = end;
	}

	free(values[misc]);
    }

    args[argc] = NULL;
    *argPtr = args;

    return 0;
}

int devInitDriverDisk(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps *modDepsPtr, int flags, char * mntPoint,
		      struct driverDiskInfo * ddi) {
    int badDisk = 0;
    char from[200];
    struct stat sb;
    char * diskName;
    int fd;
    char * fileCheck[] = { "rhdd-6.1", "modinfo", "modules.dep", "pcitable",
			    NULL };
    char ** fnPtr;

    for (fnPtr = fileCheck; *fnPtr; fnPtr++) {
	sprintf(from, "%s/%s", mntPoint, *fnPtr);
	if (access(from, R_OK)) {
	    logMessage("cannot find %s; bad driver disk", from);
	    badDisk = 1;
	}
    }

    sprintf(from, "%s/rhdd-6.1", mntPoint);
    stat(from, &sb);
    if (!sb.st_size)
	badDisk = 1;

    if (badDisk) return 1;

    diskName = malloc(sb.st_size + 1);
    fd = open(from, O_RDONLY);
    read(fd, diskName, sb.st_size);
    if (diskName[sb.st_size - 1] == '\n')
	sb.st_size--;
    diskName[sb.st_size] = '\0';
    close(fd);

    ddi->title = strdup(diskName);

    sprintf(from, "%s/modinfo", mntPoint);

    fd = isysReadModuleInfo(from, modInfo, ddi);

    sprintf(from, "%s/modules.dep", mntPoint);
    mlLoadDeps(modDepsPtr, from);
    sprintf(from, "%s/pcitable", mntPoint);
    pciReadDrivers(from);

    return 0;
}

int devLoadDriverDisk(moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps *modDepsPtr, int flags, int cancelNotBack,
		      int askForExistence, char * device) {
    int rc;
    int done = 0;
    struct driverDiskInfo * ddi;

    ddi = calloc(sizeof(*ddi), 1);

    do { 
	if (askForExistence) {
	    rc = newtWinChoice(_("Devices"), _("Yes"),
			       _("No"),
			       _("Do you have a driver disk?"));
	    if (rc == 2) return LOADER_BACK;
	}

	eject(device);
	rc = newtWinChoice(_("Devices"), _("OK"), 
		cancelNotBack ? _("Cancel") : _("Back"),
		_("Insert your driver disk and press \"OK\" to continue."));

	if (rc == 2) return LOADER_BACK;

	mlLoadModule("vfat", NULL, modLoaded, (*modDepsPtr), NULL, modInfo, 
		     flags);

	ddi->device = strdup(device);
	ddi->mntDevice = malloc(strlen(device) + 10);
	sprintf(ddi->mntDevice, "/tmp/%s", device);

	devMakeInode(ddi->device, ddi->mntDevice);

	ddi->fs = "vfat";
	logMessage("trying to mount device %s", ddi->mntDevice);
	if (doPwMount(ddi->mntDevice, "/tmp/drivers", ddi->fs, 1, 0, NULL, 
		      NULL)) {
	    ddi->fs = "ext2";
	    if (doPwMount(ddi->mntDevice, "/tmp/drivers", ddi->fs, 1, 0, NULL, 
			  NULL))
		newtWinMessage(_("Error"), _("OK"), 
			       _("Failed to mount driver disk."));
	}


	if (devInitDriverDisk(modInfo, modLoaded, modDepsPtr, flags, 
			      "/tmp/drivers", ddi))
	    newtWinMessage(_("Error"), _("OK"),
		_("The floppy disk you inserted is not a valid driver disk "
		  "for this release of Red Hat Linux."));
	else
	    done = 1;

	umount("/tmp/drivers");
    } while (!done);

    return 0;
}

struct sortModuleList {
    int index;
    moduleInfoSet modInfo;
};

static int sortDrivers(const void * a, const void * b) {
    const struct sortModuleList * one = a;
    const struct sortModuleList * two = b;

    return strcmp(one->modInfo->moduleList[one->index].description,
		  one->modInfo->moduleList[two->index].description);
}

static int pickModule(moduleInfoSet modInfo, enum driverMajor type,
		      moduleList modLoaded, moduleDeps * modDepsPtr, 
		      struct moduleInfo * suggestion,
		      struct moduleInfo ** modp, int * specifyParams,
		      char * ddDevice, int flags) {
    int i;
    newtComponent form, text, listbox, checkbox, ok, back;
    newtGrid buttons, grid, subgrid;
    char specifyParameters = *specifyParams ? '*' : ' ';
    struct newtExitStruct es;
    struct sortModuleList * sortedOrder;
    int numSorted;

    do {
	sortedOrder = malloc(sizeof(*sortedOrder) * modInfo->numModules);
	numSorted = 0;

	for (i = 0; i < modInfo->numModules; i++) {
	    if (modInfo->moduleList[i].major == type && 
		!mlModuleInList(modInfo->moduleList[i].moduleName, modLoaded)) {
		sortedOrder[numSorted].index = i;
		sortedOrder[numSorted++].modInfo = modInfo;
	    }
	}	

	if (!numSorted) {
	    /* If nothing appears in this list, force them to insert
	       a driver disk. */
	    i = devLoadDriverDisk(modInfo, modLoaded, modDepsPtr, flags, 0,
				  1, ddDevice);
	    if (i) return i;
	    continue;
	}

	qsort(sortedOrder, numSorted, sizeof(*sortedOrder), sortDrivers);

	text = newtTextboxReflowed(-1, -1, _("Which driver should I try?. "
		"If the driver you need does not appear in this list, and "
		"you have a separate driver disk, please press F2."),
				    30, 0, 10, 0);

	listbox = newtListbox(-1, -1, 6, 
			NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);

	buttons = newtButtonBar(_("OK"), &ok, _("Back"), &back, NULL);
	checkbox = newtCheckbox(-1, -1, _("Specify module parameters"),
				specifyParameters, NULL, &specifyParameters);

	form = newtForm(NULL, NULL, 0);
	newtFormAddHotKey(form, NEWT_KEY_F2);

	for (i = 0; i < numSorted; i++) {
	    int num = sortedOrder[i].index;

	    newtListboxAppendEntry(listbox, 
				   modInfo->moduleList[num].description,
				   (void *) num);
	    if (modp && (modInfo->moduleList + num) == *modp)
		newtListboxSetCurrentByKey(listbox, (void *) num);
	}

	subgrid = newtGridVStacked(NEWT_GRID_COMPONENT, listbox,
				   NEWT_GRID_COMPONENT, checkbox, NULL);
	grid = newtGridBasicWindow(text, subgrid, buttons);
	newtGridAddComponentsToForm(grid, form, 1);
	newtGridWrappedWindow(grid, _("Devices"));

	newtFormRun(form, &es);

	i = (int) newtListboxGetCurrent(listbox);

	newtGridFree(grid, 1);
	newtFormDestroy(form);
	newtPopWindow();

	free(sortedOrder);

	if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
	    return LOADER_BACK;
	} else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
	    devLoadDriverDisk(modInfo, modLoaded, modDepsPtr, flags, 0, 0,
			      ddDevice);
	    continue;
	} else {
	    break;
	}
    } while (1);

    *specifyParams = (specifyParameters != ' ');
    *modp = modInfo->moduleList + i;

    return 0;
}

int devDeviceMenu(enum driverMajor type, moduleInfoSet modInfo, 
		  moduleList modLoaded, moduleDeps * modDepsPtr, 
		  char * ddDevice, int flags, char ** moduleName) {
    struct moduleInfo * mod = NULL;
    enum { S_MODULE, S_ARGS, S_DONE } stage = S_MODULE;
    int rc;
    char ** args = NULL, ** arg;
    int specifyArgs = 0;

    while (stage != S_DONE) {
    	switch (stage) {
	  case S_MODULE:
	    if ((rc = pickModule(modInfo, type, modLoaded, modDepsPtr, mod, 
				 &mod, &specifyArgs, ddDevice, flags)))
		return LOADER_BACK;
	    stage = S_ARGS;
	    break;

	  case S_ARGS:
	    if (specifyArgs) {
		rc = getModuleArgs(mod, &args);
		if (rc) {
		    stage = S_MODULE;
		    break;
		}
	    }
	    stage = S_DONE;
	    break;

	  case S_DONE:
	}
    }

    if (mod->major == DRIVER_SCSI) {
	scsiWindow(mod->moduleName);
	sleep(1);
    }
    rc = mlLoadModule(mod->moduleName, mod->locationID, modLoaded, 
		      *modDepsPtr, args, modInfo, flags);
    if (mod->major == DRIVER_SCSI) newtPopWindow();

    if (args) {
	for (arg = args; *arg; arg++)
	    free(*arg);
	free(args);
    }

    if (rc)
	newtWinMessage(_("Error"), _("OK"), _("Failed to insert %s module."),
		       mod->moduleName);

    if (!rc && moduleName)
        *moduleName = mod->moduleName;
    
    return rc;
}

char * extractModule(struct driverDiskInfo * ddi, char * modName) {
    char * pattern[] = { NULL, NULL };
    struct utsname un;
    gzFile from;
    gzFile to;
    int first = 1;
    int fd;
    char * buf;
    struct stat sb;
    int rc;
    int failed;
    char * toPath;
    char * chptr;

    uname(&un);

    /* strip off BOOT, -SMP, whatever */
    chptr = un.release + strlen(un.release) - 1;
    while (!isdigit(*chptr)) chptr--;
    *(chptr + 1) = '\0';

    pattern[0] = alloca(strlen(modName) + strlen(un.release) + 5);
    sprintf(pattern[0], "%s*/%s.o", un.release, modName);
    logMessage("extracting pattern %s", pattern[0]);

    if (ddi->device)
	devMakeInode(ddi->device, ddi->mntDevice);

    while (1) {
	failed = 0;

	if (doPwMount(ddi->mntDevice, "/tmp/drivers", ddi->fs, 1, 0, 
		      NULL, NULL))
	    failed = 1;

	if (failed && !first) {
	    newtWinMessage(_("Error"), _("OK"), 
		    _("Failed to mount driver disk: %s."), strerror(errno));
	} else if (!failed) {
	    if ((fd = open("/tmp/drivers/rhdd-6.1", O_RDONLY)) < 0)
		failed = 1;
	    if (!failed) {
		fstat(fd, &sb);
		buf = malloc(sb.st_size + 1);
		read(fd, buf, sb.st_size);
		if (buf[sb.st_size - 1] == '\n')
		    sb.st_size--;
		buf[sb.st_size] = '\0';
		close(fd);

		failed = strcmp(buf, ddi->title);
		free(buf);
	    }

	    if (failed && !first) {
		umount("/tmp/drivers");
		newtWinMessage(_("Error"), _("OK"),
			_("The wrong diskette was inserted."));
	    }
	}

	if (!failed) {
	    from = gzopen("/tmp/drivers/modules.cgz", "r");
	    toPath = malloc(strlen(modName) + 30);
	    sprintf(toPath, "/tmp/modules/%s", modName);
	    mkdirChain(toPath);
	    strcat(toPath, "/modules.cgz");
	    to = gzopen(toPath, "w");

	    myCpioFilterArchive(from, to, pattern);

	    gzclose(from);
	    gzclose(to);
	    umount("/tmp/drivers");

	    sprintf(toPath, "/tmp/modules/%s", modName);
	    return toPath;
	}

	first = 0;

	if (ddi->device)
	    eject(ddi->device);

	rc = newtWinChoice(_("Driver Disk"), _("OK"), _("Cancel"),
		_("Please insert the %s driver disk now."), ddi->title);
	if (rc == 2) return NULL;
    }
}
