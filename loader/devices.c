#include <alloca.h>
#include <ctype.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "devices.h"
#include "isys/imount.h"
#include "../isys/isys.h"
#include "lang.h"
#include "loader.h"
#include "misc.h"
#include "modules.h"
#include "windows.h"

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
	    values[i] = malloc(strlen(mod->args[i].arg) + 2);
	    strcpy(values[i], mod->args[i].arg);
	    strcat(values[i], "=");
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

int devCopyDriverDisk(moduleInfoSet modInfo, moduleList modLoaded, 
		      moduleDeps modDeps, int flags, char * mntPoint) {
    char * files[] = { "modules.cgz", "modinfo", "modules.dep", NULL };
    char * dirName;
    char ** file;
    int badDisk = 0;
    static int diskNum = 0;
    char from[200], to[200];

    sprintf(from, "%s/rhdd-6.1", mntPoint);
    if (access(from, R_OK))
	badDisk = 1;

    dirName = malloc(80);
    sprintf(dirName, "/tmp/DD-%d", diskNum);
    mkdir(dirName, 0755);
    for (file = files; *file; file++) {
	sprintf(from, "%s/%s", mntPoint, *file);
	sprintf(to, "%s/%s", dirName, *file);

	if (copyFile(from, to))
	    badDisk = 1;
    }

    umount("/tmp/drivers");

    if (badDisk) {
	return 1;
    }

    sprintf(from, "%s/modinfo", dirName);
    isysReadModuleInfo(from, modInfo, dirName);
    sprintf(from, "%s/modules.dep", dirName);
    mlLoadDeps(&modDeps, from);

    diskNum++;

    return 0;
}

int devLoadDriverDisk(moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps modDeps, int flags, int cancelNotBack) {
    int rc;
    int done = 0;

    do { 
	rc = newtWinChoice(_("Devices"), _("OK"), 
		cancelNotBack ? _("Cancel") : _("Back"),
		_("Insert your driver disk and press \"OK\" to continue."));

	if (rc == 2) return LOADER_BACK;

	mlLoadModule("vfat", NULL, modLoaded, modDeps, NULL, flags);

	devMakeInode("fd0", "/tmp/fd0");

	if (doPwMount("/tmp/fd0", "/tmp/drivers", "vfat", 1, 0, NULL, NULL))
	    newtWinMessage(_("Error"), _("OK"), 
			   _("Failed to mount floppy disk."));

	if (devCopyDriverDisk(modInfo, modLoaded, modDeps, 
			      flags, "/tmp/drivers"))
	    newtWinMessage(_("Error"), _("OK"),
		_("The floppy disk you inserted is not a valid driver disk "
		  "for this release of Red Hat Linux."));
	else
	    done = 1;
    } while (!done);

    return 0;
}

static int pickModule(moduleInfoSet modInfo, enum driverMajor type,
		      moduleList modLoaded, moduleDeps modDeps, 
		      struct moduleInfo * suggestion,
		      struct moduleInfo ** modp, int * specifyParams,
		      int flags) {
    int i;
    newtComponent form, text, listbox, checkbox, ok, back;
    newtGrid buttons, grid, subgrid;
    char specifyParameters = *specifyParams ? '*' : ' ';
    struct newtExitStruct es;

    do {
	if (FL_MODDISK(flags)) {
	    text = newtTextboxReflowed(-1, -1, _("Which driver should I try?. "
		    "If the driver you need does not appear in this list, and "
		    "you have a separate driver disk, please press F2."),
					30, 0, 10, 0);
	} else {
	    text = newtTextboxReflowed(-1, -1, _("Which driver should I try?"),
					20, 0, 10, 0);
	}

	listbox = newtListbox(-1, -1, 6, 
			NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);

	buttons = newtButtonBar(_("OK"), &ok, _("Back"), &back, NULL);
	checkbox = newtCheckbox(-1, -1, _("Specify module parameters"),
				specifyParameters, NULL, &specifyParameters);

	form = newtForm(NULL, NULL, 0);

	if (FL_MODDISK(flags))
	    newtFormAddHotKey(form, NEWT_KEY_F2);

	for (i = 0; i < modInfo->numModules; i++) {
	    if (modInfo->moduleList[i].major == type && 
		!mlModuleInList(modInfo->moduleList[i].moduleName, modLoaded)) {
		newtListboxAppendEntry(listbox, 
				       modInfo->moduleList[i].description,
				       (void *) i);
		if (modp && (modInfo->moduleList + i) == *modp)
		    newtListboxSetCurrentByKey(listbox, (void *) i);
	    }
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

	if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
	    return LOADER_BACK;
	} else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
	    devLoadDriverDisk(modInfo, modLoaded, modDeps, flags, 0);
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
		  moduleList modLoaded, moduleDeps modDeps, int flags,
		  char ** moduleName) {
    struct moduleInfo * mod = NULL;
    enum { S_MODULE, S_ARGS, S_DONE } stage = S_MODULE;
    int rc;
    char ** args = NULL, ** arg;
    int specifyArgs = 0;

    while (stage != S_DONE) {
    	switch (stage) {
	  case S_MODULE:
	    if ((rc = pickModule(modInfo, type, modLoaded, modDeps, mod, &mod, 
				 &specifyArgs, flags)))
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
    rc = mlLoadModule(mod->moduleName, mod->path, modLoaded, modDeps, args,
		      FL_TESTING(flags));
    if (mod->major == DRIVER_SCSI) newtPopWindow();

    if (args) {
	for (arg = args; *arg; arg++)
	    free(*arg);
	free(args);
    }

    if (!rc && moduleName)
        *moduleName = mod->moduleName;
    
    return rc;
}
