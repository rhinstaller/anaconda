/*
 * driverdisk.c - driver disk functionality
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "loader.h"
#include "log.h"
#include "loadermisc.h"
#include "lang.h"
#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"
#include "windows.h"
#include "hardware.h"

#include "../isys/isys.h"
#include "../isys/imount.h"
#include "../isys/probe.h"

static char * driverDiskFiles[] = { "modinfo", "modules.dep", "pcitable",
                                    "modules.cgz", "rhdd-6.1", NULL };



static int verifyDriverDisk(char *mntpt, int flags) {
    char ** fnPtr;
    char file[200];
    struct stat sb;

    for (fnPtr = driverDiskFiles; *fnPtr; fnPtr++) {
        sprintf(file, "%s/%s", mntpt, *fnPtr);
        if (access(file, R_OK)) {
            logMessage("cannot find %s, bad driver disk", file);
            return LOADER_BACK;
        }
    }

    /* side effect: file is still mntpt/rhdd-6.1 */
    stat(file, &sb);
    if (!sb.st_size)
        return LOADER_BACK;

    return LOADER_OK;
}

/* this copies the contents of the driver disk to a ramdisk and loads
 * the moduleinfo, etc.  assumes a "valid" driver disk mounted at mntpt */
static int loadDriverDisk(moduleInfoSet modInfo, moduleList modLoaded,
                          moduleDeps * modDepsPtr, char *mntpt, int flags) {
    char file[200], dest[200];
    char * title;
    char ** fnPtr;
    struct moduleBallLocation * location;
    struct stat sb;
    static int disknum = 0;
    int fd;

    sprintf(file, "%s/rhdd-6.1", mntpt);
    title = malloc(sb.st_size + 1);

    fd = open(file, O_RDONLY);
    read(fd, title, sb.st_size);
    if (title[sb.st_size - 1] == '\n')
        sb.st_size--;
    title[sb.st_size] = '\0';
    close(fd);

    sprintf(file, "/tmp/ramfs/DD-%d", disknum);
    mkdirChain(file);

    winStatus(40, 3, _("Loading"), _("Reading driver disk..."));

    for (fnPtr = driverDiskFiles; *fnPtr; fnPtr++) {
        sprintf(file, "%s/%s", mntpt, *fnPtr);
        sprintf(dest, "/tmp/ramfs/DD-%d/%s", disknum, *fnPtr);
        copyFile(file, dest);
    }

    location = malloc(sizeof(struct moduleBallLocation));
    location->title = strdup(title);
    location->path = sdupprintf("/tmp/ramfs/DD-%d/modules.cgz", disknum);

    sprintf(file, "%s/modinfo", mntpt);
    readModuleInfo(file, modInfo, location, 1);

    sprintf(file, "%s/modules.dep", mntpt);
    mlLoadDeps(modDepsPtr, file);

    sprintf(file, "%s/pcitable", mntpt);
    pciReadDrivers(file);

    newtPopWindow();

    disknum++;
    return 0;
}

/* Get the list of removable devices (floppy/cdrom) available.  Used to
 * find suitable devices for update disk / driver disk source.  
 * Returns the number of devices.  ***devNames will be a NULL-terminated list
 * of device names
 */
int getRemovableDevices(char *** devNames) {
    struct device **devices, **floppies, **cdroms;
    int numDevices = 0;
    int i = 0, j = 0;

    floppies = probeDevices(CLASS_FLOPPY, 
                            BUS_IDE | BUS_SCSI | BUS_MISC, PROBE_ALL);
    cdroms = probeDevices(CLASS_CDROM, BUS_IDE | BUS_SCSI, PROBE_ALL);

    /* we should probably take detached into account here, but it just
     * means we use a little bit more memory than we really need to */
    if (floppies)
        for (i = 0; floppies[i]; i++) numDevices++;
    if (cdroms)
        for (i = 0; cdroms[i]; i++) numDevices++;

    /* JKFIXME: better error handling */
    if (!numDevices) {
        logMessage("no devices found to load drivers from");
        return numDevices;
    }

    devices = malloc((numDevices + 1) * sizeof(**devices));

    i = 0;
    if (floppies)
        for (j = 0; floppies[j]; j++) 
            if (floppies[j]->detached == 0) devices[i++] = floppies[j];
    if (cdroms)
        for (j = 0; cdroms[j]; j++) 
            if (cdroms[j]->detached == 0) devices[i++] = cdroms[j];

    devices[i] = NULL;
    numDevices = i;

    for (i = 0; devices[i]; i++) {
        logMessage("devices[%d] is %s", i, devices[i]->device);
    }

    *devNames = malloc((numDevices + 1) * sizeof(*devNames));
    for (i = 0; devices[i] && (i < numDevices); i++)
        (*devNames)[i] = strdup(devices[i]->device);
    free(devices);

    if (i != numDevices)
        logMessage("somehow numDevices != len(devices)");

    return numDevices;
}

/* Prompt for loading a driver from "media"
 *
 * class: type of driver to load.
 * usecancel: if 1, use cancel instead of back
 */
int loadDriverFromMedia(int class, moduleList modLoaded, 
                        moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                        struct knownDevices * kd, int flags, int usecancel) {

    char * device = NULL;
    char ** devNames = NULL;
    enum { DEV_DEVICE, DEV_INSERT, DEV_LOAD, DEV_PROBE, 
           DEV_DONE } stage = DEV_DEVICE;
    int rc, i, num = 0;

    while (stage != DEV_DONE) {
        switch(stage) {
        case DEV_DEVICE:
            rc = getRemovableDevices(&devNames);
            if (rc == 0)
                return LOADER_BACK;

            startNewt(flags);
            rc = newtWinMenu(_("Driver Disk Source"),
                             _("You have multiple devices which could serve "
                               "as sources for a driver disk.  Which would "
                               "you like to use?"), 40, 10, 10,
                             rc < 6 ? rc : 6, devNames,
                             &num, _("OK"), 
                             (usecancel) ? _("Cancel") : _("Back"), NULL);

            if (rc == 2) {
                free(devNames);
                return LOADER_BACK;
            }
            device = strdup(devNames[num]);
            free(devNames);

            stage = DEV_INSERT;
        case DEV_INSERT: {
            char * buf;

            buf = sdupprintf(_("Insert your driver disk into /dev/%s "
                               "and press \"OK\" to continue."), device);
            rc = newtWinChoice(_("Insert Driver Disk"), _("OK"), _("Back"),
                               buf);
            if (rc == 2) {
                stage = DEV_DEVICE;
                break;
            }

            devMakeInode(device, "/tmp/dddev");
            logMessage("trying to mount %s", device);
            if (doPwMount("/tmp/dddev", "/tmp/drivers", "vfat", 1, 0, NULL, NULL)) {
                if (doPwMount("/tmp/dddev", "/tmp/drivers", "ext2", 1, 0, NULL, NULL)) {
                    newtWinMessage(_("Error"), _("OK"),
                                   _("Failed to mount driver disk."));
                    stage = DEV_INSERT;
                    break;
                }
            }

            rc = verifyDriverDisk("/tmp/drivers", flags);
            if (rc == LOADER_BACK) {
                umount("/tmp/drivers");
                stage = DEV_INSERT;
                break;
            }

            stage = DEV_LOAD;
            break;
        }
        case DEV_LOAD: {
            int found = 0, before = 0;

            if (class != CLASS_UNSPEC) {
                for (i = 0; i < kd->numKnown; i++) {
                    if (kd->known[i].class == class) {
                        stage = DEV_DONE;
                        before++;
                        break;
                    }
                }
            } else {
                before = kd->numKnown;
            }

            rc = loadDriverDisk(modInfo, modLoaded, modDepsPtr, 
                                "/tmp/drivers", flags);
            umount("/tmp/drivers");
            if (rc == LOADER_BACK) {
                stage = DEV_INSERT;
                break;
            }
            /* fall through to probing */
            stage = DEV_PROBE;

        case DEV_PROBE:
            busProbe(modInfo, modLoaded, *modDepsPtr, 0, kd, flags);

            if (class != CLASS_UNSPEC) {
                for (i = 0; i < kd->numKnown; i++) {
                    if (kd->known[i].class == class) {
                        stage = DEV_DONE;
                        found++;
                        break;
                    }
                }
            } else {
                found = kd->numKnown;
            }

            if (found > before) {
                stage = DEV_DONE;
                break;
            }

            /* we don't have any more modules of the proper class.  ask
             * them to manually load */
            rc = newtWinTernary(_("Error"), _("Manually choose"), 
                                _("Continue"), _("Load another disk"),
                                _("No devices of the appropriate type were "
                                  "found on this driver disk.  Would you "
                                  "like to manually select the driver, "
                                  "continue anyway, or load another "
                                  "driver disk?"));
            
            if (rc == 2) {
                /* if they choose to continue, just go ahead and continue */
                stage = DEV_DONE;
            } else if (rc == 3) {
                /* if they choose to load another disk, back to the 
                 * beginning with them */
                stage = DEV_DEVICE;
            } else {
                rc = chooseManualDriver(class, modLoaded, modDepsPtr, modInfo,
                                        kd, flags);
                /* if they go back from a manual driver, we'll ask again.
                 * if they load something, assume it's what we need */
                if (rc == LOADER_OK) {
                    updateKnownDevices(kd);
                    stage = DEV_DONE;
                }
            }

            break;
        }
                           

        case DEV_DONE:
            break;
        }
    }

    return LOADER_OK;
}


/* looping way to load driver disks */
int loadDriverDisks(int class, moduleList modLoaded, 
                    moduleDeps * modDepsPtr, moduleInfoSet modInfo, 
                    struct knownDevices * kd, int flags) {
    int rc;
    loadDriverFromMedia(CLASS_UNSPEC, modLoaded, modDepsPtr, modInfo, 
                        kd, flags, 1);

    do {
        rc = newtWinChoice(_("More Driver Disks?"), _("Yes"), _("No"),
                           _("Do you wish to load any more driver disks?"));
        if (rc != 1)
            break;
        loadDriverFromMedia(CLASS_UNSPEC, modLoaded, modDepsPtr, modInfo, 
                            kd, flags, 1);
    } while (1);
}
