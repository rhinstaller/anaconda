/*
 * driverdisk.c - driver disk functionality
 *
 * Copyright (C) 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
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
 * Author(s): Jeremy Katz <katzj@redhat.com>
 */

#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <glib.h>

#include <blkid/blkid.h>

#include <glob.h>
#include <rpm/rpmlib.h>
#include <sys/utsname.h>

#include "copy.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "fwloader.h"
#include "method.h"
#include "modules.h"
#include "moduleinfo.h"
#include "windows.h"
#include "hardware.h"
#include "driverdisk.h"
#include "getparts.h"
#include "dirbrowser.h"

#include "nfsinstall.h"
#include "urlinstall.h"

#include "rpmextract.h"

#include "../isys/isys.h"
#include "../isys/imount.h"
#include "../isys/eddsupport.h"
#include "../isys/log.h"

/* boot flags */
extern uint64_t flags;

/* modprobe DD mode */
int modprobeDDmode(void)
{
    FILE *f = fopen("/etc/depmod.d/ddmode.conf", "w");
    if (f) {
        struct utsname unamedata;

        if (uname(&unamedata))
            fprintf(f, " pblacklist /lib/modules\n");
        else
            fprintf(f, " pblacklist /lib/modules/%s\n", unamedata.release);
        fclose(f);
    }

    return f==NULL;
}

int modprobeNormalmode(void)
{
    /* remove depmod overrides */
    if (unlink("/etc/depmod.d/ddmode.conf")) {
        logMessage(ERROR, "removing ddmode.conf failed");
        return -1;
    }

    /* run depmod to refresh modules db */
    if (system("depmod -a")) {
        logMessage(ERROR, "depmod -a failed");
        return -1;
    }

    return 0;
}

/*
 * check if the RPM in question provides
 * Provides: userptr
 * we use it to check kernel-modules-<kernelversion>
 */
int dlabelProvides(const char* dep, void *userptr)
{
    char *kernelver = (char*)userptr;

    logMessage(DEBUGLVL, "Provides: %s\n", dep);

    return strcmp(dep, kernelver);
}

/*
 * during cpio extraction, only extract files we need
 * eg. module .ko files and firmware directory
 */
int dlabelFilter(const char* name, const struct stat *fstat, void *userptr)
{
    int l = strlen(name);

    logMessage(DEBUGLVL, "Unpacking %s\n", name);

    /* we want firmware files */
    if (!strncmp("lib/firmware/", name, 13)) return 0; 

    if (l<3)
        return 1;
    l-=3;

    /* and we want only .ko files */
    if (strcmp(".ko", name+l))
        return 1;

    /* TODO we are unpacking kernel module, read it's description */

    return 0;
}

char* moduleDescription(const char* modulePath)
{
    char *command = NULL;
    FILE *f = NULL;
    char *description = NULL;
    int size;

    checked_asprintf(&command, "modinfo --description '%s'", modulePath);
    f = popen(command, "r");
    free(command);

    if (f==NULL)
        return NULL;

    description = malloc(sizeof(char)*256);
    if (!description)
        return NULL;

    size = fread(description, 1, 255, f);
    if (size == 0) {
        free(description);
        return NULL;
    }

    description[size-1]=0; /* strip the trailing newline */
    pclose(f);

    return description;
}

int globErrFunc(const char *epath, int eerrno)
{
    /* TODO check fatal errors */

    return 0;
}

int dlabelUnpackRPMDir(char* rpmdir, char* destination)
{
    char *kernelver;
    struct utsname unamedata;
    char *oldcwd;
    char *globpattern;
    int rc;

    /* get current working directory */ 
    oldcwd = getcwd(NULL, 0);
    if (!oldcwd) {
        logMessage(ERROR, "getcwd() failed: %m");
        return 1;
    }

    /* set the cwd to destination */
    if (chdir(destination)) {
        logMessage(ERROR, "We weren't able to CWD to \"%s\": %m", destination);
        free(oldcwd);
        return 1;
    }

    /* get running kernel version */
    rc = uname(&unamedata);
    checked_asprintf(&kernelver, "kernel-modules-%s",
            rc ? "unknown" : unamedata.release);
    logMessage(DEBUGLVL, "Kernel version: %s\n", kernelver);

    checked_asprintf(&globpattern, "%s/*.rpm", rpmdir);
    glob_t globres;
    char** globitem;
    if (!glob(globpattern, GLOB_NOSORT|GLOB_NOESCAPE, globErrFunc, &globres)) {
        /* iterate over all rpm files */
        globitem = globres.gl_pathv;
        while (globres.gl_pathc>0 && globitem != NULL) {
            explodeRPM(*globitem, dlabelFilter, dlabelProvides, NULL, kernelver);
        }
        globfree(&globres);
        /* end of iteration */
    }
    free(globpattern);

    /* restore CWD */
    if (chdir(oldcwd)) {
        logMessage(WARNING, "We weren't able to restore CWD to \"%s\": %m", oldcwd);
    }

    /* cleanup */
    free(kernelver);
    free(oldcwd);
    return rc;
}


static char * driverDiskFiles[] = { "repodata", NULL };

static int verifyDriverDisk(char *mntpt) {
    char ** fnPtr;
    char file[200];
    struct stat sb;

    /* check for dd descriptor */
    sprintf(file, "%s/rhdd3", mntpt);
    if (access(file, R_OK)) {
        logMessage(ERROR, "can't find driver disk identifier, bad "
                          "driver disk");
        return LOADER_BACK;
    }

    /* side effect: file is still mntpt/ddident */
    stat(file, &sb);
    if (!sb.st_size)
        return LOADER_BACK;
    for (fnPtr = driverDiskFiles; *fnPtr; fnPtr++) {
        snprintf(file, 200, "%s/%s/%s", mntpt, getProductArch(), *fnPtr);
        if (access(file, R_OK)) {
            logMessage(ERROR, "cannot find %s, bad driver disk", file);
            return LOADER_BACK;
        }
    }

    return LOADER_OK;
}

static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

/* this copies the contents of the driver disk to a ramdisk and loads
 * the moduleinfo, etc.  assumes a "valid" driver disk mounted at mntpt */
static int loadDriverDisk(struct loaderData_s *loaderData, char *mntpt) {
    /* FIXME moduleInfoSet modInfo = loaderData->modInfo; */
    char file[200], dest[200], src[200];
    char *title;
    char *fwdir = NULL;
    struct moduleBallLocation * location;
    struct stat sb;
    static int disknum = 0;
    int fd, ret;

    /* check for new version */
    sprintf(file, "%s/rhdd3", mntpt);
    if (access(file, R_OK)) {
      /* this can't happen, we already verified it! */
      return LOADER_BACK;
    }
    stat(file, &sb);
    title = malloc(sb.st_size + 1);

    fd = open(file, O_RDONLY);
    ret = read(fd, title, sb.st_size);
    if (title[sb.st_size - 1] == '\n')
        sb.st_size--;
    title[sb.st_size] = '\0';
    close(fd);

    sprintf(file, DD_RPMDIR_TEMPLATE, disknum);
    mkdirChain(file);
    mkdirChain(DD_MODULES);
    mkdirChain(DD_FIRMWARE);

    if (!FL_CMDLINE(flags)) {
        startNewt();
        winStatus(40, 3, _("Loading"), _("Reading driver disk"));
    }

    location = malloc(sizeof(struct moduleBallLocation));
    location->title = strdup(title);
    checked_asprintf(&location->path, DD_MODULES);

    sprintf(dest, DD_RPMDIR_TEMPLATE, disknum);
    sprintf(src, "%s/rpms/%s", mntpt, getProductArch());
    copyDirectory(src, dest, copyWarnFn, copyErrorFn);

    /* unpack packages from dest into location->path */
    if (dlabelUnpackRPMDir(dest, DD_EXTRACTED)) {
        /* fatal error, log this and jump to exception handler */
        logMessage(ERROR, "Error unpacking RPMs from driver disc no.%d",
                disknum);
        goto loadDriverDiscException;
    }

    /* run depmod to refresh modules db */
    if (system("depmod -a")) {
      /* this is not really fatal error, it might still work, log it */
      logMessage(ERROR, "Error running depmod -a for driverdisc no.%d", disknum);
    }

    checked_asprintf(&fwdir, DD_FIRMWARE);
    if (!access(fwdir, R_OK|X_OK)) {
        add_fw_search_dir(loaderData, fwdir);
        stop_fw_loader(loaderData);
        start_fw_loader(loaderData);
    }
    free(fwdir);

    /* TODO generate and read module info
     *
     * sprintf(file, "%s/modinfo", mntpt);
     * readModuleInfo(file, modInfo, location, 1);
     */

loadDriverDiscException:

    if (!FL_CMDLINE(flags))
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
    struct device **devs;
    int numDevices = 0;
    int i = 0;

    devs = getDevices(DEVICE_DISK | DEVICE_CDROM);

    if (!devs)
        return numDevices;

    for (i = 0; devs[i] ; i++) {
        if (devs[i]->priv.removable) {
            *devNames = realloc(*devNames, (numDevices + 2) * sizeof(char *));
            (*devNames)[numDevices] = strdup(devs[i]->device);
            (*devNames)[numDevices+1] = NULL;
            numDevices ++;
        }
    }
    if (!numDevices) {
        logMessage(ERROR, "no devices found to load drivers from");
    }
    return numDevices;
}

/* Prompt for loading a driver from "media"
 *
 * class: type of driver to load.
 * usecancel: if 1, use cancel instead of back
 */
int loadDriverFromMedia(int class, struct loaderData_s *loaderData,
                        int usecancel, int noprobe) {
    char * device = NULL, * part = NULL, * ddfile = NULL;
    char ** devNames = NULL;
    enum { DEV_DEVICE, DEV_PART, DEV_CHOOSEFILE, DEV_LOADFILE, 
           DEV_INSERT, DEV_LOAD, DEV_PROBE, 
           DEV_DONE } stage = DEV_DEVICE;
    int rc, num = 0;
    int dir = 1;
    int found = 0, before = 0;

    while (stage != DEV_DONE) {
        switch(stage) {
        case DEV_DEVICE:
            rc = getRemovableDevices(&devNames);
            if (rc == 0)
                return LOADER_BACK;

            /* we don't need to ask which to use if they only have one */
            if (rc == 1) {
                device = strdup(devNames[0]);
                free(devNames);
                if (dir == -1)
                    return LOADER_BACK;
                
                stage = DEV_PART;
                break;
            }
            dir = 1;

            startNewt();
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

            stage = DEV_PART;
        case DEV_PART: {
            char ** part_list = getPartitionsList(device);
            int nump = 0, num = 0;

            /* Do not crash if the device disappeared */
            if (!part_list) {
                stage = DEV_DEVICE;
                break;
            }

            if (part != NULL)
                free(part);

            if ((nump = lenPartitionsList(part_list)) == 0) {
                if (dir == -1)
                    stage = DEV_DEVICE;
                else
                    stage = DEV_INSERT;
                break;
            }
            dir = 1;

            startNewt();
            rc = newtWinMenu(_("Driver Disk Source"),
                             _("There are multiple partitions on this device "
                               "which could contain the driver disk image.  "
                               "Which would you like to use?"), 40, 10, 10,
                             nump < 6 ? nump : 6, part_list, &num, _("OK"),
                             _("Back"), NULL);

            if (rc == 2) {
                freePartitionsList(part_list);
                stage = DEV_DEVICE;
                dir = -1;
                break;
            }

            part = strdup(part_list[num]);
            stage = DEV_CHOOSEFILE;

        }

        case DEV_CHOOSEFILE: {
            if (part == NULL) {
                logMessage(ERROR, "somehow got to choosing file with a NULL part, going back");
                stage = DEV_PART;
                break;
            }
            /* make sure nothing is mounted when we get here */
            num = umount("/tmp/dpart");
            if (num == -1) { 
                logMessage(ERROR, "error unmounting: %m");
                if ((errno != EINVAL) && (errno != ENOENT))
                    exit(1);
            }

            logMessage(INFO, "trying to mount %s as partition", part);
            if (doPwMount(part, "/tmp/dpart", "auto", "ro", NULL)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Failed to mount partition."));
                stage = DEV_PART;
                break;
            }

            ddfile = newt_select_file(_("Select driver disk image"),
                                      _("Select the file which is your driver "
                                        "disk image."),
                                      "/tmp/dpart", NULL);
            if (ddfile == NULL) {
                umount("/tmp/dpart");
                stage = DEV_PART;
                dir = -1;
                break;
            }
            dir = 1;

            stage = DEV_LOADFILE;
        }

        case DEV_LOADFILE: {
            if (ddfile == NULL) {
                logMessage(DEBUGLVL, "trying to load dd from NULL");
                stage = DEV_CHOOSEFILE;
                break;
            }
            if (dir == -1) {
                umountLoopback("/tmp/drivers", "/dev/loop6");
                unlink("/tmp/drivers");
                ddfile = NULL;
                stage = DEV_CHOOSEFILE;
                break;
            }
            if (mountLoopback(ddfile, "/tmp/drivers", "/dev/loop6")) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Failed to load driver disk from file."));
                stage = DEV_CHOOSEFILE;
                break;
            }
            stage = DEV_LOAD;
            break;
        }

        case DEV_INSERT: {
            char * buf;

            checked_asprintf(&buf,
                             _("Insert your driver disk into /dev/%s "
                               "and press \"OK\" to continue."), device);

            rc = newtWinChoice(_("Insert Driver Disk"), _("OK"), _("Back"),
                               buf);
            free(buf);
            if (rc == 2) {
                stage = DEV_DEVICE;
                dir = -1;
                break;
            }
            dir = 1;

            logMessage(INFO, "trying to mount %s", device);
            if (doPwMount(device, "/tmp/drivers", "auto", "ro", NULL)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Failed to mount driver disk."));
                stage = DEV_INSERT;
                break;
            }

            rc = verifyDriverDisk("/tmp/drivers");
            if (rc == LOADER_BACK) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Driver disk is invalid for this "
                                 "release of %s."), getProductName());
                umount("/tmp/drivers");
                stage = DEV_INSERT;
                break;
            }

            stage = DEV_LOAD;
            break;
        }
        case DEV_LOAD: {
            struct device ** devices;

	    before = 0;
	    found = 0;

            devices = getDevices(class);
            if (devices)
                for(; devices[before]; before++);

            rc = loadDriverDisk(loaderData, "/tmp/drivers");
            umount("/tmp/drivers");
            if (rc == LOADER_BACK) {
                dir = -1;
                if (ddfile != NULL)
                    stage = DEV_CHOOSEFILE;
                else
                    stage = DEV_INSERT;
                break;
            }
            /* fall through to probing */
            stage = DEV_PROBE;

            if (ddfile != NULL) {
                umountLoopback("/tmp/drivers", "/dev/loop6");
                unlink("/tmp/drivers");
                umount("/tmp/dpart");
            }
        }

        case DEV_PROBE: {
            struct device ** devices;

            /* if they didn't specify that we should probe, then we should
             * just fall out */
            if (noprobe) {
                stage = DEV_DONE;
                break;
            }

            busProbe(0);

            devices = getDevices(class);
            if (devices)
                for(; devices[found]; found++);

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
                rc = chooseManualDriver(class, loaderData);
                /* if they go back from a manual driver, we'll ask again.
                 * if they load something, assume it's what we need */
                if (rc == LOADER_OK) {
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
int loadDriverDisks(int class, struct loaderData_s *loaderData) {
    int rc;

    rc = newtWinChoice(_("Driver disk"), _("Yes"), _("No"), 
                       _("Do you have a driver disk?"));
    if (rc != 1)
        return LOADER_OK;

    rc = loadDriverFromMedia(DEVICE_ANY, loaderData, 1, 0);
    if (rc == LOADER_BACK)
        return LOADER_OK;

    do {
        rc = newtWinChoice(_("More Driver Disks?"), _("Yes"), _("No"),
                           _("Do you wish to load any more driver disks?"));
        if (rc != 1)
            break;
        loadDriverFromMedia(DEVICE_ANY, loaderData, 0, 0);
    } while (1);

    return LOADER_OK;
}

static void loadFromLocation(struct loaderData_s * loaderData, char * dir) {
    if (verifyDriverDisk(dir) == LOADER_BACK) {
        logMessage(ERROR, "not a valid driver disk");
        return;
    }

    loadDriverDisk(loaderData, dir);
    busProbe(0);
}

void getDDFromSource(struct loaderData_s * loaderData, char * src) {
    char *path = "/tmp/dd.img";
    int unlinkf = 0;

    if (!strncmp(src, "nfs:", 4)) {
        unlinkf = 1;
        if (getFileFromNfs(src + 4, "/tmp/dd.img", loaderData)) {
            logMessage(ERROR, "unable to retrieve driver disk: %s", src);
            return;
        }
    } else if (!strncmp(src, "ftp://", 6) || !strncmp(src, "http", 4)) {
        unlinkf = 1;
        if (getFileFromUrl(src, "/tmp/dd.img", loaderData)) {
            logMessage(ERROR, "unable to retrieve driver disk: %s", src);
            return;
        }
    /* FIXME: this is a hack so that you can load a driver disk from, eg, 
     * scsi cdrom drives */
#if !defined(__s390__) && !defined(__s390x__)
    } else if (!strncmp(src, "cdrom", 5)) {
        loadDriverDisks(DEVICE_ANY, loaderData);
        return;
#endif
    } else if (!strncmp(src, "path:", 5)) {
	path = src + 5;
    } else {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown driver disk kickstart source: %s"), src);
        return;
    }

    if (!mountLoopback(path, "/tmp/drivers", "/dev/loop6")) {
        loadFromLocation(loaderData, "/tmp/drivers");
        umountLoopback("/tmp/drivers", "/dev/loop6");
        unlink("/tmp/drivers");
        if (unlinkf) unlink(path);
    }

}

static void getDDFromDev(struct loaderData_s * loaderData, char * dev);

void useKickstartDD(struct loaderData_s * loaderData,
                    int argc, char ** argv) {
    char * dev = NULL;
    char * biospart = NULL, * p = NULL; 
    gchar *fstype = NULL, *src = NULL;
    gint usebiosdev = 0;
    gchar **remaining = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksDDOptions[] = {
        /* The --type option is deprecated and now has no effect. */
        { "type", 0, 0, G_OPTION_ARG_STRING, &fstype, NULL, NULL },
        { "source", 0, 0, G_OPTION_ARG_STRING, &src, NULL, NULL },
        { "biospart", 0, 0, G_OPTION_ARG_INT, &usebiosdev, NULL, NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksDDOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("The following invalid argument was specified for "
                         "the kickstart driver disk command: %s"),
                       optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        g_strfreev(remaining);
        return;
    }

    g_option_context_free(optCon);

    if ((remaining != NULL) && (g_strv_length(remaining) == 1)) {
        dev = remaining[0];
    }

    if (!dev && !src) {
        logMessage(ERROR, "bad arguments to kickstart driver disk command");
        return;
    }

    if (usebiosdev != 0) {
        p = strchr(dev,'p');
        if (!p){
            logMessage(ERROR, "Bad argument for biospart");
            return;
        }
        *p = '\0';
        
        biospart = getBiosDisk(dev);
        if (biospart == NULL) {
            logMessage(ERROR, "Unable to locate BIOS dev %s",dev);
            return;
        }
        dev = malloc(strlen(biospart) + strlen(p + 1) + 2);
        sprintf(dev, "%s%s", biospart, p + 1);
    }

    if (dev) {
        getDDFromDev(loaderData, dev);
    } else {
        getDDFromSource(loaderData, src);
    }

    g_strfreev(remaining);
    return;
}

static void getDDFromDev(struct loaderData_s * loaderData, char * dev) {
    if (doPwMount(dev, "/tmp/drivers", "auto", "ro", NULL)) {
        logMessage(ERROR, "unable to mount driver disk %s", dev);
        return;
    }

    loadFromLocation(loaderData, "/tmp/drivers");
    umount("/tmp/drivers");
    unlink("/tmp/drivers");
}


/*
 * Look for partition with specific label (part of #316481)
 */
GSList* findDriverDiskByLabel(void)
{
    char *ddLabel = "OEMDRV";
    GSList *ddDevice = NULL;
    blkid_cache bCache;
    
    int res;
    blkid_dev_iterate bIter;
    blkid_dev bDev;

    if (blkid_get_cache(&bCache, NULL)<0) {
        logMessage(ERROR, "Cannot initialize cache instance for blkid");
        return NULL;
    }
    if ((res = blkid_probe_all(bCache))<0) {
        logMessage(ERROR, "Cannot probe devices in blkid: %d", res);
        return NULL;
    }
    if ((res = blkid_probe_all_removable(bCache))<0) {
        logMessage(ERROR, "Cannot probe removable devices in blkid: %d", res);
    }

    bIter = blkid_dev_iterate_begin(bCache);
    blkid_dev_set_search(bIter, "LABEL", ddLabel);
    while ((res = blkid_dev_next(bIter, &bDev)) == 0) {
        bDev = blkid_verify(bCache, bDev);
        if (!bDev)
            continue;

        char *devname = strdup(blkid_dev_devname(bDev));
        logMessage(DEBUGLVL, "Adding driver disc %s to the list "
                             "of available DDs.", devname);
        ddDevice = g_slist_prepend(ddDevice, (gpointer)devname);
        /* Freeing bDev is taken care of by the put cache call */
    }
    blkid_dev_iterate_end(bIter);

    blkid_put_cache(bCache);

    return ddDevice;
}

int loadDriverDiskFromPartition(struct loaderData_s *loaderData, char* device)
{
    int rc;

    logMessage(INFO, "trying to mount %s", device);
    if (doPwMount(device, "/tmp/drivers", "auto", "ro", NULL)) {
        logMessage(ERROR, "Failed to mount driver disk.");
        return -1;
    }

    rc = verifyDriverDisk("/tmp/drivers");
    if (rc == LOADER_BACK) {
        logMessage(ERROR, "Driver disk is invalid for this "
                "release of %s.", getProductName());
        umount("/tmp/drivers");
        return -2;
    }

    rc = loadDriverDisk(loaderData, "/tmp/drivers");
    umount("/tmp/drivers");
    if (rc == LOADER_BACK) {
        return -3;
    }

    return 0;
}

