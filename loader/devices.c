#include <alloca.h>
#include <ctype.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "devices.h"
#include "../isys/isys.h"
#include "lang.h"
#include "loader.h"
#include "modules.h"

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

    rc = newtWinEntries(_("Module Parameters"), _("This module can take "
		    "parameters which affects its operation. If you don't "
		    "know what parameters to supply, just skip this "
		    "screen by pressing the \"Ok\" button now."),
		    40, 5, 15, 20, entries, _("Ok"), _("Back"), NULL);

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

static int pickModule(moduleInfoSet modInfo, enum driverMajor type,
		      moduleList modLoaded, struct moduleInfo * suggestion,
		      struct moduleInfo ** modp, int * specifyParams) {
    int i;
    newtComponent form, text, listbox, answer, checkbox, ok, back;
    newtGrid buttons, grid, subgrid;
    char specifyParameters = *specifyParams ? '*' : ' ';

    text = newtTextboxReflowed(-1, -1, _("Which driver should I try?"),
				20, 0, 10, 0);
    listbox = newtListbox(-1, -1, 6, NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);

    for (i = 0; i < modInfo->numModules; i++) {
	if (modInfo->moduleList[i].major == type && 
	    !mlModuleInList(modInfo->moduleList[i].moduleName, modLoaded)) {
	    newtListboxAppendEntry(listbox, modInfo->moduleList[i].description,
				   (void *) i);
	    if (modp && (modInfo->moduleList + i) == *modp)
		newtListboxSetCurrentByKey(listbox, (void *) i);
	}
    }

    buttons = newtButtonBar(_("Ok"), &ok, _("Back"), &back, NULL);
    checkbox = newtCheckbox(-1, -1, _("Specify module parameters"),
			    specifyParameters, NULL, &specifyParameters);
    subgrid = newtGridVStacked(NEWT_GRID_COMPONENT, listbox,
			       NEWT_GRID_COMPONENT, checkbox, NULL);
    grid = newtGridBasicWindow(text, subgrid, buttons);

    newtGridWrappedWindow(grid, _("Devices"));

    form = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, form, 1);

    answer = newtRunForm(form);
    newtPopWindow();

    i = (int) newtListboxGetCurrent(listbox);

    newtGridFree(grid, 1);
    newtFormDestroy(form);

    if (answer == back) return LOADER_BACK;
    
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
	    if ((rc = pickModule(modInfo, type, modLoaded, mod, &mod, 
				 &specifyArgs)))
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

    rc = mlLoadModule(mod->moduleName, modLoaded, modDeps, args,
		      FL_TESTING(flags));

    if (args) {
	for (arg = args; *arg; arg++)
	    free(*arg);
	free(args);
    }

    if (!rc && moduleName)
        *moduleName = mod->moduleName;
    
    return rc;
}
