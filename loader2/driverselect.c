/*
 * driverselect.c - functionality for manually selecting drivers
 *
 * Erik Troan <ewt@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997-2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <ctype.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "modules.h"
#include "moduleinfo.h"
#include "../isys/probe.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "hardware.h"

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

static int getManualModuleArgs(struct moduleInfo * mod, char *** moduleArgs) {
    newtGrid grid, buttons;
    newtComponent text, f, ok, back, entry;
    struct newtExitStruct es;
    int done = 0, i;
    char * buf;
    char *argsEntry = "";

    if (*moduleArgs) {
        for (i = 0; (*moduleArgs)[i]; i++)
            argsEntry = strcat(argsEntry, (*moduleArgs)[i]);
    }

    f = newtForm(NULL, NULL, 0);
    buf = sdupprintf(_("Please enter any parameters which you wish to pass "
                       "to the %s module separated by spaces.  If you don't "
                       "know what parameters to supply, skip this screen "
                       "by pressing the \"OK\" button.  A list of available "
                       "options can be obtained by pressing the F1 key."), 
                     mod->moduleName);
    text = newtTextboxReflowed(-1, -1, buf, 60, 0, 10, 0);
    entry = newtEntry(-1, -1, argsEntry, 50, &argsEntry, 
                      NEWT_ENTRY_SCROLL);
    
    newtFormAddHotKey(f, NEWT_KEY_F1);
    newtFormAddHotKey(f, NEWT_KEY_F12);
    
    buttons = newtButtonBar(_("OK"), &ok, _("Back"), &back, NULL);
    
    grid = newtCreateGrid(1, 3);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, entry, 
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);
    
    newtGridWrappedWindow(grid, _("Enter Module Parameters"));
    newtGridAddComponentsToForm(grid, f, 1);
    
    do {
        newtFormRun(f, &es);

        if (es.reason  == NEWT_EXIT_COMPONENT && es.u.co == back) {
            done = -1;
        } else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F1) {
            logMessage("need to pop up 'help' with module options here");
            /* JKFIXME: ^^^ */
        } else {
            done = 1;
        }
    } while (done == 0);

    newtGridFree(grid, 1);

    if (done == -1) {
        newtFormDestroy(f);
        newtPopWindow();

        return LOADER_BACK;
    }
    logMessage("specified args of %s for %s", argsEntry, mod->moduleName);

    if (strlen(argsEntry) > 0) {
        int numAlloced = 5;
        char * start;
        char * end;

        i = 0;

        *moduleArgs = malloc((numAlloced + 1) * sizeof(*moduleArgs));
        start = argsEntry;
        while (start && *start) {
            end = start;
            while (!isspace(*end) && *end) end++;
            *end = '\0';
            (*moduleArgs)[i++] = strdup(start);
            start = end + 1;
            *end = ' ';
            start = strchr(end, ' ');
            if (start) start++;

            if (i >= numAlloced) {
                numAlloced += 5;
                *moduleArgs = realloc(*moduleArgs, 
                                      sizeof(*moduleArgs) * (numAlloced + 1));
            }
        }
        (*moduleArgs)[i] = NULL;
    }

    newtFormDestroy(f);
    newtPopWindow();

    return LOADER_OK;
}

int chooseManualDriver(int class, moduleList modLoaded, moduleDeps modDeps,
                       moduleInfoSet modInfo, struct knownDevices * kd, 
                       int flags) {
    int i, numSorted, num = 0, done = 0;
    enum driverMajor type;
    struct sortModuleList * sortedOrder;
    char giveArgs = ' ';
    char ** moduleArgs = NULL;

    newtComponent text, f, ok, back, argcheckbox, listbox;
    newtGrid grid, buttons;
    struct newtExitStruct es;

    if (class == CLASS_NETWORK)
        type = DRIVER_NET;
    else if ((class == CLASS_SCSI) || (class == CLASS_HD) || 
             (class == CLASS_CDROM))
        type = DRIVER_SCSI;
    else if (class == CLASS_UNSPEC)
        type = -1;
    else {
        logMessage("unknown device class %d specified; aborting manual "
                   "selection", class);
        return LOADER_ERROR;
    }

    sortedOrder = malloc(sizeof(*sortedOrder) * modInfo->numModules);
    numSorted = 0;

    for (i = 0; i < modInfo->numModules; i++) {
        if (mlModuleInList(modInfo->moduleList[i].moduleName, modLoaded) ||
            !modInfo->moduleList[i].description ||
            ((type >= 0) && (type != modInfo->moduleList[i].major)))
            continue;
        sortedOrder[numSorted].index = i;
        sortedOrder[numSorted++].modInfo = modInfo;
    }

    if (numSorted == 0) {
        /* JKFIXME: if no drivers to load, should we ask about driver disk? */
        logMessage("no drivers to load");
        return LOADER_BACK;
    }

    qsort(sortedOrder, numSorted, sizeof(*sortedOrder), sortDrivers);

    f = newtForm(NULL, NULL, 0);

    text = newtTextboxReflowed(-1, -1,
                               _("Please select the driver below which you "
                                 "wish to load.  If it does not appear and "
                                 "you have a driver disk, press F2."),
                               60, 0, 10, 0);

    listbox = newtListbox(-1, -1, 6, NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);

    buttons = newtButtonBar(_("OK"), &ok, _("Back"), &back, NULL);
    argcheckbox = newtCheckbox(-1, -1, _("Specify optional module arguments"),
                               giveArgs, NULL, &giveArgs);

    newtFormAddHotKey(f, NEWT_KEY_F2);
    newtFormAddHotKey(f, NEWT_KEY_F12);

    for (i = 0; i < numSorted; i++) {
        newtListboxAppendEntry(listbox, sdupprintf("%s (%s)", 
                                                   modInfo->moduleList[sortedOrder[i].index].description,
                                                   modInfo->moduleList[sortedOrder[i].index].moduleName), (void *) sortedOrder[i].index);
    }

    grid = newtCreateGrid(1, 4);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text, 0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, listbox, 
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_COMPONENT, argcheckbox,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 3, NEWT_GRID_SUBGRID, buttons, 
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);
    newtGridWrappedWindow(grid, _("Select Device Driver to Load"));

    newtGridAddComponentsToForm(grid, f, 1);

    do { 
        newtFormRun(f, &es);

        num = (int) newtListboxGetCurrent(listbox);

        if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
            done = -1;
        } else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
            logMessage("need to go to load a driver disk here");
            /* JKFIXME: ^^^ */
            done = -1;
        } else {
            if (giveArgs != ' ') {
                i = getManualModuleArgs(&(modInfo->moduleList[num]), 
                                         &moduleArgs);
                if (i == LOADER_BACK)
                    done = 0;
                else
                    done = 1;
            } else {
                done = 1;
            }
        }
    } while (done == 0);

    newtGridFree(grid, 1);
    newtFormDestroy(f);
    newtPopWindow();

    if (done == -1) 
        return LOADER_BACK;


    mlLoadModule(modInfo->moduleList[num].moduleName, modLoaded, modDeps,
                 modInfo, moduleArgs, flags);
    updateKnownDevices(kd);
    free(sortedOrder);

    return LOADER_OK;
}


