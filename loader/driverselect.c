/*
 * driverselect.c - functionality for manually selecting drivers
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002  Red Hat, Inc.
 * All rights reserved.
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
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <ctype.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#include "../isys/log.h"

#include "modules.h"
#include "moduleinfo.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "driverdisk.h"

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

static int getManualModuleArgs(struct moduleInfo * mod, gchar *** moduleArgs) {
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
    checked_asprintf(&buf,
                     _("Please enter any parameters which you wish to pass "
                       "to the %s module separated by spaces.  If you don't "
                       "know what parameters to supply, skip this screen "
                       "by pressing the \"OK\" button."), mod->moduleName);

    text = newtTextboxReflowed(-1, -1, buf, 60, 0, 10, 0);
    entry = newtEntry(-1, -1, argsEntry, 50, (const char **) &argsEntry, 
                      NEWT_ENTRY_SCROLL);
    
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
        } else {
            done = 1;
        }
    } while (done == 0);

    free(buf);
    newtGridFree(grid, 1);

    if (done == -1) {
        newtFormDestroy(f);
        newtPopWindow();

        return LOADER_BACK;
    }
    logMessage(INFO, "specified args of %s for %s", argsEntry, mod->moduleName);

    if (strlen(argsEntry) > 0) {
        *moduleArgs = g_strsplit(argsEntry, " ", 0);
    }

    newtFormDestroy(f);
    newtPopWindow();

    return LOADER_OK;
}

int chooseManualDriver(int class, struct loaderData_s *loaderData) {
    int i, numSorted, num = 0, done = 0;
    enum driverMajor type;
    struct sortModuleList * sortedOrder;
    char giveArgs = ' ';
    gchar **moduleArgs = NULL;
    moduleInfoSet modInfo = loaderData->modInfo;

    newtComponent text, f, ok, back, argcheckbox, listbox;
    newtGrid grid, buttons;
    struct newtExitStruct es;

    if (class == DEVICE_NETWORK)
        type = DRIVER_NET;
    else if (class == DEVICE_DISK || class == DEVICE_CDROM)
        type = DRIVER_SCSI;
    else
        type = DRIVER_ANY;

    do {
        sortedOrder = malloc(sizeof(*sortedOrder) * modInfo->numModules);
        numSorted = 0;
        
        for (i = 0; i < modInfo->numModules; i++) {
            sortedOrder[numSorted].index = i;
            sortedOrder[numSorted++].modInfo = modInfo;
        }
        
        if (numSorted == 0) {
            i = newtWinChoice(_("No drivers found"), _("Load driver disk"), 
                              _("Back"), _("No drivers were found to manually "
                                           "insert.  Would you like to use "
                                           "a driver disk?"));
            if (i != 1)
                return LOADER_BACK;
            
            loadDriverFromMedia(class, loaderData, 1, 1);
            continue;
        } else {
            break;
        }
    } while (1);
        
    qsort(sortedOrder, numSorted, sizeof(*sortedOrder), sortDrivers);

    f = newtForm(NULL, NULL, 0);

    text = newtTextboxReflowed(-1, -1,
                               _("Please select the driver below which you "
                                 "wish to load.  If it does not appear and "
                                 "you have a driver disk, press F2."),
                               60, 0, 10, 0);

    listbox = newtListbox(-1, -1, 6, NEWT_FLAG_SCROLL | NEWT_FLAG_RETURNEXIT);
    newtListboxSetWidth(listbox, 55);

    buttons = newtButtonBar(_("OK"), &ok, _("Back"), &back, NULL);
    argcheckbox = newtCheckbox(-1, -1, _("Specify optional module arguments"),
                               giveArgs, NULL, &giveArgs);

    newtFormAddHotKey(f, NEWT_KEY_F2);
    newtFormAddHotKey(f, NEWT_KEY_F12);

    for (i = 0; i < numSorted; i++) {
        char *buf = NULL;

        checked_asprintf(&buf, "%s (%s)", 
                         modInfo->moduleList[sortedOrder[i].index].description,
                         modInfo->moduleList[sortedOrder[i].index].moduleName);

        newtListboxAppendEntry(listbox, buf, 
                INT_TO_POINTER(sortedOrder[i].index));
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

        num = POINTER_TO_INT(newtListboxGetCurrent(listbox));

        if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
            done = -1;
        } else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
            done = -2;
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
    if (done == -2) {
        loadDriverFromMedia(class, loaderData, 1, 1);
        return chooseManualDriver(class, loaderData);
    }

    mlLoadModule(modInfo->moduleList[num].moduleName, moduleArgs);
    free(sortedOrder);

    if (moduleArgs) {
        g_strfreev(moduleArgs);
    }

    return LOADER_OK;
}
