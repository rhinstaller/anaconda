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
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>
#include <glib.h>

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

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/eddsupport.h"
#include "../isys/log.h"

/* boot flags */
extern uint64_t flags;

/* given a partition device and directory, tries to mount hd install image */
static char * setupIsoImages(char * device, char * dirName, char * location) {
    int rc = 0;
    char *url = NULL, *dirspec, *updpath, *path;

    logMessage(INFO, "mounting device %s for hard drive install", device);

    if (doPwMount(device, "/mnt/isodir", "auto", "ro", NULL))
        return NULL;

    checked_asprintf(&dirspec, "/mnt/isodir%.*s",
                     (int) (strrchr(dirName, '/') - dirName), dirName);
    checked_asprintf(&path, "/mnt/isodir%s", dirName);

    if (path) {
        logMessage(INFO, "Path to stage2 image is %s", path);

        rc = copyFile(path, "/tmp/install.img");
        rc = mountStage2("/tmp/install.img");

        free(path);

        if (rc) {
            umountLoopback("/mnt/runtime", "/dev/loop0");
            umount("/mnt/isodir");
            goto err;
        }

        checked_asprintf(&updpath, "%s/updates.img", dirspec);

        logMessage(INFO, "Looking for updates for HD in %s", updpath);
        copyUpdatesImg(updpath);
        free(updpath);

        checked_asprintf(&updpath, "%s/product.img", dirspec);

        logMessage(INFO, "Looking for product for HD in %s", updpath);
        copyProductImg(updpath);

        free(updpath);
        free(dirspec);
        umount("/mnt/isodir");

        checked_asprintf(&url, "hd:%s:/%s", device,
                         dirName ? dirName : ".");

        return url;
    } else {
        free(dirspec);
        free(path);

        if (rc) {
            umount("/mnt/isodir");
            return NULL;
        }
    }

err:
    newtWinMessage(_("Error"), _("OK"),
                   _("An error occured finding the installation image "
                     "on your hard drive.  Please check your images and "
                     "try again."));
    return NULL;
}

/* setup hard drive based install from a partition with a filesystem and
 * ISO images on that filesystem
 */
char * mountHardDrive(struct installMethod * method,
		      char * location, struct loaderData_s * loaderData) {
    int rc;
    int i;

    newtComponent listbox, label, dirEntry, form, okay, back, text;
    struct newtExitStruct es;
    newtGrid entryGrid, grid, buttons;

    int done = 0;
    char * dir = strdup("");
    char * tmpDir;
    char * url = NULL;
    char * buf, *substr;
    int numPartitions;

    char **partition_list;
    char *selpart;
    char *kspartition = NULL, *ksdirectory = NULL;

    /* handle kickstart/stage2= data first if available */
    if (loaderData->method == METHOD_HD && loaderData->stage2Data) {
        kspartition = ((struct hdInstallData *)loaderData->stage2Data)->partition;
        ksdirectory = ((struct hdInstallData *)loaderData->stage2Data)->directory;
        logMessage(INFO, "partition is %s, dir is %s", kspartition, ksdirectory);

        /* if exist, duplicate */
        if (kspartition)
            kspartition = strdup(kspartition);
        if (ksdirectory) {
            ksdirectory = strdup(ksdirectory);
        } else {
            ksdirectory = strdup("/images/install.img");
        }

        if (!kspartition || !ksdirectory) {
            logMessage(ERROR, "missing partition or directory specification");
            loaderData->method = -1;

            if (loaderData->inferredStage2)
                loaderData->invalidRepoParam = 1;
        } else {
            /* if we start with /dev, strip it (#121486) */
            char *kspart = kspartition;
            if (!strncmp(kspart, "/dev/", 5))
                kspart = kspart + 5;

            url = setupIsoImages(kspart, ksdirectory, location);
            if (!url) {
                logMessage(ERROR, "unable to find %s installation images on hd",
                           getProductName());
                loaderData->method = -1;

                if (loaderData->inferredStage2)
                    loaderData->invalidRepoParam = 1;
            } else {
                free(kspartition);
                free(ksdirectory);
                return url;
            }
        }
    } else {
        kspartition = NULL;
        ksdirectory = NULL;
    }

    /* if we're here its either because this is interactive, or the */
    /* hd kickstart directive was faulty and we have to prompt for  */
    /* location of harddrive image                                  */

    partition_list = NULL;
    while (!done) {
        /* if we're doing another pass free this up first */
        if (partition_list)
            freePartitionsList(partition_list);

        partition_list = getPartitionsList(NULL);
        numPartitions = lenPartitionsList(partition_list);

        /* no partitions found, try to load a device driver disk for storage */
        if (!numPartitions) {
            rc = newtWinChoice(_("Hard Drives"), _("Yes"), _("Back"),
                               _("You don't seem to have any hard drives on "
                                 "your system! Would you like to configure "
                                 "additional devices?"));
            if (rc == 2) {
                loaderData->stage2Data = NULL;
                return NULL;
            }

            rc = loadDriverFromMedia(DEVICE_DISK, loaderData, 0, 0);
            continue;
        }

        /* now find out which partition has the stage2 image */
        checked_asprintf(&buf, _("What partition and directory on that "
                                 "partition holds the installation image "
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
            free(kspartition);
            kspartition = NULL;
        }

        label = newtLabel(-1, -1, _("Directory holding image:"));

        dirEntry = newtEntry(28, 11, dir, 28, (const char **) &tmpDir,
                             NEWT_ENTRY_SCROLL);

        /* if we had ks data around use it to prime entry, then get rid of it*/
        if (ksdirectory) {
            newtEntrySet(dirEntry, ksdirectory, 1);
            free(ksdirectory);
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

        free(dir);
        if (tmpDir && *tmpDir) {
            /* Protect from form free. */
            dir = strdup(tmpDir);
        } else  {
            dir = strdup("");
        }

        newtFormDestroy(form);
        newtPopWindow();

        if (es.reason == NEWT_EXIT_COMPONENT && es.u.co == back) {
            loaderData->stage2Data = NULL;
            return NULL;
        } else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
            rc = loadDriverFromMedia(DEVICE_DISK, loaderData, 0, 0);
            continue;
        }

        logMessage(INFO, "partition %s selected", selpart);

        /* If the user-provided URL points at a repo instead of a stage2
         * image, fix that up now.
         */
        substr = strstr(dir, ".img");
        if (!substr || (substr && *(substr+4) != '\0')) {
            checked_asprintf(&dir, "%s/images/install.img", dir);
        }

        loaderData->invalidRepoParam = 1;

        url = setupIsoImages(selpart, dir, location);
        if (!url) {
            newtWinMessage(_("Error"), _("OK"), 
                           _("Device %s does not appear to contain "
                             "an installation image."), selpart, getProductName());
            continue;
        }

        done = 1; 
    }

    free(dir);

    return url;
}

void setKickstartHD(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char *p;
    gchar *biospart = NULL, *partition = NULL, *dir = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksHDOptions[] = {
        { "biospart", 0, 0, G_OPTION_ARG_STRING, &biospart, NULL, NULL },
        { "partition", 0, 0, G_OPTION_ARG_STRING, &partition, NULL, NULL },
        { "dir", 0, 0, G_OPTION_ARG_STRING, &dir, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromHD");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksHDOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to HD kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (biospart) {
        char * dev;

        p = strchr(biospart,'p');
        if(!p){
            logMessage(ERROR, "Bad argument for --biospart");
            return;
        }
        *p = '\0';
        dev = getBiosDisk(biospart);
        if (dev == NULL) {
            logMessage(ERROR, "Unable to location BIOS partition %s", biospart);
            return;
        }
        partition = malloc(strlen(dev) + strlen(p + 1) + 2);
        sprintf(partition, "%s%s", dev, p + 1);
    }

    loaderData->method = METHOD_HD;
    loaderData->stage2Data = calloc(sizeof(struct hdInstallData *), 1);
    if (partition)
        ((struct hdInstallData *)loaderData->stage2Data)->partition = partition;
    if (dir)
        ((struct hdInstallData *)loaderData->stage2Data)->directory = dir;

    logMessage(INFO, "results of hd ks, partition is %s, dir is %s", partition,
               dir);
}

int kickstartFromHD(char *kssrc) {
    int rc;
    char *p, *np = NULL, *tmpstr, *ksdev, *kspath;

    logMessage(INFO, "getting kickstart file from harddrive");

    /* format is hd:[device]:/path/to/ks.cfg */
    /* split up pieces */
    tmpstr = strdup(kssrc);
    p = strchr(tmpstr, ':');
    if (p)
        np = strchr(p+1, ':');
    
    /* no second colon, assume its the old format of                     */
    /*        hd:[device]/path/to/ks.cfg                                 */
    /* this format is bad however because some devices have '/' in them! */
    if (!np)
        np = strchr(p+1, '/');

    if (!p || !np) {
        logMessage(WARNING, "Format of command line is ks=hd:[device]:/path/to/ks.cfg");
        free(tmpstr);
        return 1;
    }

    *np = '\0';
    ksdev = p+1;
    kspath = np+1;

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


int kickstartFromBD(char *kssrc) {
    int rc;
    char *p, *np = NULL, *r = NULL, *tmpstr, *ksdev, *kspath, *biosksdev;

    logMessage(INFO, "getting kickstart file from biosdrive");

    /* format is bd:[device]:/path/to/ks.cfg */
    /* split of pieces */
    tmpstr = strdup(kssrc);
    p = strchr(tmpstr, ':');
    if (p)
        np = strchr(p+1, ':');
    
    if (!p || !np) {
        logMessage(WARNING, "Format of command line is ks=bd:device:/path/to/ks.cfg");
        free(tmpstr);
        return 1;
    }

    *np = '\0';
    kspath = np+1;

    r = strchr(p+1,'p');
    if(!r){
        logMessage(INFO, "Format of biosdisk is 80p1");
        free(tmpstr);
        return 1;
    }                                                          

    *r = '\0';
    biosksdev = getBiosDisk((p + 1));
    if(!biosksdev){
        startNewt();
        newtWinMessage(_("Error"), _("OK"),
                       _("Cannot find hard drive for BIOS disk %s"),
                       p + 1);
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
