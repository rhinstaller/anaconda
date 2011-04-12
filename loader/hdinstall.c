/*
 * hdinstall.c - code to set up hard drive installs
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
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
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <ctype.h>
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>
#include <glib.h>

#include "dirbrowser.h"
#include "driverdisk.h"
#include "hdinstall.h"
#include "getparts.h"
#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "mediacheck.h"
#include "cdinstall.h"
#include "windows.h"

#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/eddsupport.h"
#include "../pyanaconda/isys/log.h"

/* boot flags */
extern uint64_t flags;

/* format is hd:device:/path */
static void parseDeviceAndDir(char *url, char **device, char **dir) {
    char *token, *src = NULL;

    if (!url)
        return;

    /* Skip over the leading hd: if present. */
    if (!strncmp(url, "hd:", 3))
        url += 3;

    logMessage(DEBUGLVL, "parseDeviceAndDir url: |%s|", url);

    src = strdup(url);
    token = strtok(src, ":");
    if (!token)
        return;

    *device = strdup(token);

    token = strtok(NULL, ":");
    if (!token)
        *dir = strdup("/");
    else
        *dir = strdup(token);

    logMessage(DEBUGLVL, "parseDeviceAndDir device: |%s|", *device);
    logMessage(DEBUGLVL, "parseDeviceAndDir dir: |%s|", *dir);
}

static int ends_with_iso(char *dirname, struct dirent *ent) {
    char *suffix;

    if (ent->d_type != DT_REG)
        return 0;

    suffix = rindex(ent->d_name, '.');
    return (suffix && !strcmp(suffix, ".iso"));
}

int loadHdImages(struct loaderData_s *loaderData) {
    char *device = NULL, *dir = NULL, *path;

    logMessage(DEBUGLVL, "looking for extras for HD install");

    if (!loaderData->instRepo)
        return 0;

    parseDeviceAndDir(loaderData->instRepo, &device, &dir);

    if (doPwMount(device, "/mnt/install/isodir", "auto", "ro", NULL))
        return 0;

    if (dir[0] == '/') {
        checked_asprintf(&path, "/mnt/install/isodir%s/updates.img", dir);
    } else {
        checked_asprintf(&path, "/mnt/install/isodir/%s/updates.img", dir);
    }

    logMessage(INFO, "Looking for updates for HD in %s", path);
    copyUpdatesImg(path);
    free(path);

    if (dir[0] == '/') {
        checked_asprintf(&path, "/mnt/install/isodir%s/product.img", dir);
    } else {
        checked_asprintf(&path, "/mnt/install/isodir/%s/product.img", dir);
    }

    logMessage(INFO, "Looking for product for HD in %s", path);
    copyProductImg(path);

    free(device);
    free(dir);
    free(path);
    umount("/mnt/install/isodir");

    return 1;
}

int promptForHardDrive(struct loaderData_s *loaderData) {
    int rc;
    int i;

    newtComponent listbox, label, dirEntry, form, okay, back, text;
    struct newtExitStruct es;
    newtGrid entryGrid, grid, buttons;

    char * dir = g_strdup("");
    char * tmpDir;
    char * buf;
    int numPartitions;

    char **files;
    char **partition_list;
    char *selpart;
    char *kspartition = NULL, *ksdirectory = NULL;

    partition_list = NULL;
    while (1) {
        /* if we're doing another pass free this up first */
        if (partition_list)
            g_strfreev(partition_list);

        partition_list = getPartitionsList(NULL);
        numPartitions = g_strv_length(partition_list);

        /* no partitions found, try to load a device driver disk for storage */
        if (!numPartitions) {
            rc = newtWinChoice(_("Hard Drives"), _("Yes"), _("Back"),
                               _("You don't seem to have any hard drives on "
                                 "your system! Would you like to configure "
                                 "additional devices?"));
            if (rc == 2) {
                loaderData->instRepo = NULL;
                return LOADER_BACK;
            }

            rc = loadDriverFromMedia(DEVICE_DISK, loaderData, 0, 0, NULL);
            continue;
        }

        /* now find out which partition has the stage2 image */
        checked_asprintf(&buf, _("What partition and directory on that "
                                 "partition holds an installation tree "
                                 "for %s?  If you don't see the disk drive "
                                 "you're using listed here, press F2 to "
                                 "configure additional devices."),
                         getProductName());

        text = newtTextboxReflowed(-1, -1, buf, 62, 5, 5, 0);
        free(buf);

        listbox = newtListbox(-1, -1, numPartitions > 5 ? 5 : numPartitions,
                              NEWT_FLAG_RETURNEXIT | 
                              (numPartitions > 5 ? NEWT_FLAG_SCROLL : 0));

        for (i = 0; i < numPartitions; i++)
            newtListboxAppendEntry(listbox,partition_list[i],partition_list[i]);

        /* if we had ks data around use it to prime entry, then get rid of it*/
        if (kspartition) {
            newtListboxSetCurrentByKey(listbox, kspartition);
            g_free(kspartition);
            kspartition = NULL;
        }

        label = newtLabel(-1, -1, _("Directory holding tree:"));

        dirEntry = newtEntry(28, 11, dir, 28, (const char **) &tmpDir,
                             NEWT_ENTRY_SCROLL);

        /* if we had ks data around use it to prime entry, then get rid of it*/
        if (ksdirectory) {
            newtEntrySet(dirEntry, ksdirectory, 1);
            g_free(ksdirectory);
            ksdirectory = NULL;
        }

        entryGrid = newtGridHStacked(NEWT_GRID_COMPONENT, label,
                                     NEWT_GRID_COMPONENT, dirEntry,
                                     NEWT_GRID_EMPTY);

        buttons = newtButtonBar(_("OK"), &okay, _("Back"), &back, NULL);

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
        newtFormAddHotKey(form, NEWT_KEY_F2);
        newtFormAddHotKey(form, NEWT_KEY_F12);

        newtGridAddComponentsToForm(grid, form, 1);
        newtGridFree(grid, 1);

        newtFormRun(form, &es);

        selpart = newtListboxGetCurrent(listbox);

        g_free(dir);
        if (tmpDir && *tmpDir) {
            /* Protect from form free. */
            dir = g_strdup(tmpDir);
        } else  {
            dir = g_strdup("");
        }

        newtFormDestroy(form);
        newtPopWindow();

        if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
            loaderData->instRepo = NULL;
            return LOADER_BACK;
        } else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
            rc = loadDriverFromMedia(DEVICE_DISK, loaderData, 0, 0, NULL);
            continue;
        }

        logMessage(INFO, "partition %s selected", selpart);

        /* Now verify the ISO images pointed to contain an installation source. */
        if (doPwMount(selpart, "/mnt/install/isodir", "auto", "ro", NULL)) {
            logMessage(ERROR, "couldn't mount %s to verify images", selpart);
            continue;
        }

        if (dir[0] == '/') {
            checked_asprintf(&buf, "/mnt/install/isodir%s", dir);
        } else {
            checked_asprintf(&buf, "/mnt/install/isodir/%s", dir);
        }

        files = get_file_list(buf, ends_with_iso);
        if (!files) {
            newtWinMessage(_("Error"), _("OK"),
                           _("That directory does not contain an installable tree."));
            umount("/mnt/install/isodir");
            free(buf);
            continue;
        }

        free(buf);

        /* mount the first image and check for a .treeinfo file */
        if (dir[0] == '/') {
            checked_asprintf(&buf, "/mnt/install/isodir%s/%s", dir, files[0]);
        } else {
            checked_asprintf(&buf, "/mnt/install/isodir/%s/%s", dir, files[0]);
        }

        if (doPwMount(buf, "/mnt/install/testmnt", "auto", "ro", NULL)) {
            free(buf);
            newtWinMessage(_("Error"), _("OK"),
                           _("That directory does not contain an installable tree."));
            umount("/mnt/install/isodir");
            continue;
        }

        free(buf);

        if (access("/mnt/install/testmnt/.treeinfo", R_OK)) {
            newtWinMessage(_("Error"), _("OK"),
                           _("That directory does not contain an installable tree."));
            umount("/mnt/install/testmnt");
            umount("/mnt/install/isodir");
            continue;
        }

        umount("/mnt/install/testmnt");
        umount("/mnt/install/isodir");
        break;
    }

    checked_asprintf(&loaderData->instRepo, "hd:%s:/%s", selpart, dir);
    g_free(dir);
    loaderData->method = METHOD_HD;

    return LOADER_OK;
}

int kickstartFromHD(char *kssrc) {
    int rc;
    char *ksdev, *kspath;

    logMessage(INFO, "getting kickstart file from harddrive");
    parseDeviceAndDir(kssrc, &ksdev, &kspath);

    if (!ksdev || !kspath) {
        logMessage(WARNING, "Format of command line is ks=hd:[device]:/path/to/ks.cfg");
        return 1;
    }

    logMessage(INFO, "Loading ks from device %s on path %s", ksdev, kspath);
    if ((rc=getKickstartFromBlockDevice(ksdev, kspath))) {
        if (rc == 3) {
            startNewt();
            newtWinMessage(_("Error"), _("OK"),
                           _("Cannot find kickstart file on hard drive."));
        }

        free(ksdev);
        free(kspath);
        return 1;
    }

    free(ksdev);
    free(kspath);
    return 0;
}


int kickstartFromBD(char *kssrc) {
    int rc;
    char *r = NULL, *ksdev, *kspath, *biosksdev;

    logMessage(INFO, "getting kickstart file from biosdrive");
    parseDeviceAndDir(kssrc, &ksdev, &kspath);

    if (!ksdev || !kspath) {
        logMessage(WARNING, "Format of command line is ks=bd:device:/path/to/ks.cfg");
        return 1;
    }

    r = strchr(ksdev, 'p');
    if (!r) {
        logMessage(INFO, "Format of biosdisk is 80p1");
        free(ksdev);
        free(kspath);
        return 1;
    }

    *r = '\0';
    biosksdev = getBiosDisk(ksdev);
    if(!biosksdev){
        startNewt();
        newtWinMessage(_("Error"), _("OK"),
                       _("Cannot find hard drive for BIOS disk %s"),
                       ksdev);
        free(ksdev);
        free(kspath);
        return 1;
    }


    ksdev = malloc(strlen(biosksdev) + 3);
    sprintf(ksdev, "%s%s", biosksdev, r + 1);
    logMessage(INFO, "Loading ks from device %s on path %s", ksdev, kspath);
    if ((rc=getKickstartFromBlockDevice(ksdev, kspath))) {
        if (rc == 3) {
            startNewt();
            newtWinMessage(_("Error"), _("OK"),
                           _("Cannot find kickstart file on hard drive."));
        }
        return 1;
    }

    return 0;
}

/* vim:set shiftwidth=4 softtabstop=4: */
