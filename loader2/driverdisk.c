/*
 * driverdisk.c - driver disk functionality
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 2002-2007 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <sys/types.h>
#include <dirent.h>

#include <blkid/blkid.h>

#include "loader.h"
#include "log.h"
#include "loadermisc.h"
#include "lang.h"
#include "fwloader.h"
#include "method.h"
#include "modules.h"
#include "moduledeps.h"
#include "moduleinfo.h"
#include "windows.h"
#include "hardware.h"
#include "driverdisk.h"
#include "getparts.h"
#include "dirbrowser.h"

#include "nfsinstall.h"
#include "urlinstall.h"

#include "../isys/isys.h"
#include "../isys/imount.h"
#include "../isys/eddsupport.h"

/* boot flags */
extern uint64_t flags;

static char * driverDiskFiles[] = { "modinfo", "modules.dep", 
                                    "modules.cgz", "modules.alias", NULL };

static int verifyDriverDisk(char *mntpt) {
    char ** fnPtr;
    char file[200];
    struct stat sb;

    for (fnPtr = driverDiskFiles; *fnPtr; fnPtr++) {
        sprintf(file, "%s/%s", mntpt, *fnPtr);
        if (access(file, R_OK)) {
            logMessage(ERROR, "cannot find %s, bad driver disk", file);
            return LOADER_BACK;
        }
    }

    /* check for both versions */
    sprintf(file, "%s/rhdd", mntpt);
    if (access(file, R_OK)) {
        logMessage(DEBUGLVL, "not a new format driver disk, checking for old");
        sprintf(file, "%s/rhdd-6.1", mntpt);
        if (access(file, R_OK)) {
            logMessage(ERROR, "can't find either driver disk identifier, bad "
                       "driver disk");
        }
    }

    /* side effect: file is still mntpt/ddident */
    stat(file, &sb);
    if (!sb.st_size)
        return LOADER_BACK;

    return LOADER_OK;
}

/* this copies the contents of the driver disk to a ramdisk and loads
 * the moduleinfo, etc.  assumes a "valid" driver disk mounted at mntpt */
static int loadDriverDisk(struct loaderData_s *loaderData, char *mntpt) {
    moduleDeps *modDepsPtr = loaderData->modDepsPtr;
    moduleInfoSet modInfo = loaderData->modInfo;
    char file[200], dest[200];
    char * title;
    struct moduleBallLocation * location;
    struct stat sb;
    static int disknum = 0;
    int version = 1;
    int fd, ret;

    /* check for both versions */
    sprintf(file, "%s/rhdd", mntpt);
    if (access(file, R_OK)) {
        version = 0;
        sprintf(file, "%s/rhdd-6.1", mntpt);
        if (access(file, R_OK)) {
            /* this can't happen, we already verified it! */
            return LOADER_BACK;
        } 
    }
    stat(file, &sb);
    title = malloc(sb.st_size + 1);

    fd = open(file, O_RDONLY);
    ret = read(fd, title, sb.st_size);
    if (title[sb.st_size - 1] == '\n')
        sb.st_size--;
    title[sb.st_size] = '\0';
    close(fd);

    sprintf(file, "/tmp/ramfs/DD-%d", disknum);
    mkdirChain(file);

    if (!FL_CMDLINE(flags)) {
        startNewt();
        winStatus(40, 3, _("Loading"), _("Reading driver disk..."));
    }

    sprintf(dest, "/tmp/ramfs/DD-%d", disknum);
    copyDirectory(mntpt, dest);

    location = malloc(sizeof(struct moduleBallLocation));
    location->title = strdup(title);
    location->path = sdupprintf("/tmp/ramfs/DD-%d/modules.cgz", disknum);
    location->version = version;

    char *fwdir = sdupprintf("/tmp/ramfs/DD-%d/firmware", disknum);
    if (!access(fwdir, R_OK|X_OK)) {
        add_fw_search_dir(loaderData, fwdir);
        stop_fw_loader(loaderData);
        start_fw_loader(loaderData);
    }
    free(fwdir);

    sprintf(file, "%s/modinfo", mntpt);
    readModuleInfo(file, modInfo, location, 1);

    sprintf(file, "%s/modules.dep", mntpt);
    mlLoadDeps(modDepsPtr, file);

    sprintf(file, "%s/modules.alias", mntpt);
    pciReadDrivers(file);

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
    struct device **devices, **floppies, **cdroms, **disks;
    int numDevices = 0;
    int i = 0, j = 0;

    floppies = probeDevices(CLASS_FLOPPY, 
                            BUS_IDE | BUS_SCSI | BUS_MISC, PROBE_LOADED);
    cdroms = probeDevices(CLASS_CDROM, 
                          BUS_IDE | BUS_SCSI | BUS_MISC, PROBE_LOADED);
    disks = probeDevices(CLASS_HD, 
                         BUS_IDE | BUS_SCSI | BUS_MISC, PROBE_LOADED);

    /* we should probably take detached into account here, but it just
     * means we use a little bit more memory than we really need to */
    if (floppies)
        for (i = 0; floppies[i]; i++) numDevices++;
    if (cdroms)
        for (i = 0; cdroms[i]; i++) numDevices++;
    if (disks)
        for (i = 0; disks[i]; i++) numDevices++;

    /* JKFIXME: better error handling */
    if (!numDevices) {
        logMessage(ERROR, "no devices found to load drivers from");
        return numDevices;
    }

    devices = malloc((numDevices + 1) * sizeof(**devices));

    i = 0;
    if (floppies)
        for (j = 0; floppies[j]; j++) 
            if ((floppies[j]->detached == 0) && (floppies[j]->device != NULL)) 
                devices[i++] = floppies[j];
    if (cdroms)
        for (j = 0; cdroms[j]; j++) 
            if ((cdroms[j]->detached == 0) && (cdroms[j]->device != NULL)) 
                devices[i++] = cdroms[j];
    if (disks)
        for (j = 0; disks[j]; j++) 
            if ((disks[j]->detached == 0) && (disks[j]->device != NULL)) 
                devices[i++] = disks[j];

    devices[i] = NULL;
    numDevices = i;

    for (i = 0; devices[i]; i++) {
        logMessage(DEBUGLVL, "devices[%d] is %s", i, devices[i]->device);
    }

    *devNames = malloc((numDevices + 1) * sizeof(*devNames));
    for (i = 0; devices[i] && (i < numDevices); i++)
        (*devNames)[i] = strdup(devices[i]->device);
    free(devices);
    (*devNames)[i] = NULL;

    if (i != numDevices)
        logMessage(WARNING, "somehow numDevices != len(devices)");

    return numDevices;
}

/* Prompt for loading a driver from "media"
 *
 * class: type of driver to load.
 * usecancel: if 1, use cancel instead of back
 */
int loadDriverFromMedia(int class, struct loaderData_s *loaderData,
                        int usecancel, int noprobe) {
    moduleList modLoaded = loaderData->modLoaded;
    moduleDeps *modDepsPtr = loaderData->modDepsPtr;
    moduleInfoSet modInfo = loaderData->modInfo;

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

            if (part != NULL) free(part);

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
                logMessage(ERROR, "error unmounting: %s", strerror(errno));
                if ((errno != EINVAL) && (errno != ENOENT))
                    exit(1);
            }

            logMessage(INFO, "trying to mount %s as partition", part);
            devMakeInode(part + 5, "/tmp/ddpart");
            if (doPwMount("/tmp/ddpart", "/tmp/dpart", "vfat", IMOUNT_RDONLY, NULL)) {
                if (doPwMount("/tmp/ddpart", "/tmp/dpart", "ext2", IMOUNT_RDONLY, NULL)) {
                    if (doPwMount("/tmp/ddpart", "/tmp/dpart", "iso9660", IMOUNT_RDONLY, NULL)) {
                        newtWinMessage(_("Error"), _("OK"),
                                       _("Failed to mount partition."));
                        stage = DEV_PART;
                        break;
                    }
                }
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
            if(ddfile == NULL) {
                logMessage(DEBUGLVL, "trying to load dd from NULL");
                stage = DEV_CHOOSEFILE;
                break;
            }
            if (dir == -1) {
                umountLoopback("/tmp/drivers", "loop6");
                unlink("/tmp/drivers");
                ddfile = NULL;
                stage = DEV_CHOOSEFILE;
                break;
            }
            if (mountLoopback(ddfile, "/tmp/drivers", "loop6")) {
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

            buf = sdupprintf(_("Insert your driver disk into /dev/%s "
                               "and press \"OK\" to continue."), device);
            rc = newtWinChoice(_("Insert Driver Disk"), _("OK"), _("Back"),
                               buf);
            if (rc == 2) {
                stage = DEV_DEVICE;
                dir = -1;
                break;
            }
            dir = 1;

            devMakeInode(device, "/tmp/dddev");
            logMessage(INFO, "trying to mount %s", device);
            if (doPwMount("/tmp/dddev", "/tmp/drivers", "vfat", IMOUNT_RDONLY, NULL)) {
              if (doPwMount("/tmp/dddev", "/tmp/drivers", "ext2", IMOUNT_RDONLY, NULL)) {
                if (doPwMount("/tmp/dddev", "/tmp/drivers", "iso9660", IMOUNT_RDONLY, NULL)) {
                    newtWinMessage(_("Error"), _("OK"),
                                   _("Failed to mount driver disk."));
                    stage = DEV_INSERT;
                    break;
                }
              }
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

            devices = probeDevices(class, BUS_UNSPEC, PROBE_LOADED);
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
                umountLoopback("/tmp/drivers", "loop6");
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

            busProbe(modInfo, modLoaded, *modDepsPtr, 0);

            devices = probeDevices(class, BUS_UNSPEC, PROBE_LOADED);
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

    rc = loadDriverFromMedia(CLASS_UNSPEC, loaderData, 1, 0);
    if (rc == LOADER_BACK)
        return LOADER_OK;

    do {
        rc = newtWinChoice(_("More Driver Disks?"), _("Yes"), _("No"),
                           _("Do you wish to load any more driver disks?"));
        if (rc != 1)
            break;
        loadDriverFromMedia(CLASS_UNSPEC, loaderData, 0, 0);
    } while (1);

    return LOADER_OK;
}

static void loadFromLocation(struct loaderData_s * loaderData, char * dir) {
    if (verifyDriverDisk(dir) == LOADER_BACK) {
        logMessage(ERROR, "not a valid driver disk");
        return;
    }

    loadDriverDisk(loaderData, dir);
    busProbe(loaderData->modInfo, loaderData->modLoaded, *
             loaderData->modDepsPtr, 0);
}

/*
 * Utility functions to maintain linked-list of device names
 * */

struct ddlist* ddlist_add(struct ddlist *list, const char* device)
{
  struct ddlist* item;

  item = (struct ddlist*)malloc(sizeof(struct ddlist));
  if(item==NULL){
    return list;
  }

  item->device = strdup(device);
  item->next = list;

  return item;
}

int ddlist_free(struct ddlist *list)
{
  struct ddlist *next;
  int count = 0;

  while(list!=NULL){
    next = list->next;
    free(list->device);
    free(list);
    list = next;
    count++;
  }

  return count;
}


/*
 * Look for partition with specific label (part of #316481)
 */
struct ddlist* findDriverDiskByLabel(void)
{
    char *ddLabel = "OEMDRV";
    struct ddlist *ddDevice = NULL;
    blkid_cache bCache;
    struct dirent *direntry;
    DIR *sysblock;
    
    int res;
    blkid_dev_iterate bIter;
    blkid_dev bDev;

    if(blkid_get_cache(&bCache, NULL)<0){
	logMessage(ERROR, _("Cannot initialize cache instance for blkid"));
	return NULL;
    }

    /* List all block devices from /sys/block and add them to blkid db
     * libblkid should be doing that, so lets consider this as a workaround */
    sysblock = opendir("/sys/block");
    if(sysblock){
      while((direntry = readdir(sysblock))!=NULL){
	/* add only h(d?), s(d?) and s(cd?) devices */
	if(direntry->d_name[0]!='h' &&
	   direntry->d_name[0]!='s') continue;

	char *devname;
	if(asprintf(&devname, "/dev/%s", direntry->d_name)!=-1){
	  blkid_get_dev(bCache, devname, BLKID_DEV_NORMAL);
	  free(devname);
	}
      }
      closedir(sysblock);
    }

    if((res = blkid_probe_all(bCache))<0){
	logMessage(ERROR, _("Cannot probe devices in blkid: %d"), res);
	return NULL;
    }

    bIter = blkid_dev_iterate_begin(bCache);
    blkid_dev_set_search(bIter, "LABEL", ddLabel);
    while((res = blkid_dev_next(bIter, &bDev))==0){
        bDev = blkid_verify(bCache, bDev);
	if(!bDev)
	  continue;
	logMessage(DEBUGLVL, _("Adding driver disc %s to the list of available DDs."), blkid_dev_devname(bDev));
	ddDevice = ddlist_add(ddDevice, blkid_dev_devname(bDev));
	/*blkid_free_dev(bDev); -- probably taken care of by the put cache call.. it is not exposed in the API */
    }
    blkid_dev_iterate_end(bIter);
    
    blkid_put_cache(bCache);

    return ddDevice;
}

int loadDriverDiskFromPartition(struct loaderData_s *loaderData, char* device)
{
    int rc;

    logMessage(INFO, "trying to mount %s", device);
    if (doPwMount(device, "/tmp/drivers", "vfat", IMOUNT_RDONLY, NULL)) {
      if (doPwMount(device, "/tmp/drivers", "ext2", IMOUNT_RDONLY, NULL)) {
	if (doPwMount(device, "/tmp/drivers", "iso9660", IMOUNT_RDONLY, NULL)) {
	    logMessage(ERROR, _("Failed to mount driver disk."));
	    return -1;
	}
      }
    }

    rc = verifyDriverDisk("/tmp/drivers");
    if (rc == LOADER_BACK) {
	logMessage(ERROR, _("Driver disk is invalid for this "
			 "release of %s."), getProductName());
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

void getDDFromSource(struct loaderData_s * loaderData, char * src) {
    char *path = "/tmp/dd.img";
    int unlinkf = 0;

    if (!strncmp(src, "nfs:", 4)) {
        unlinkf = 1;
        if (getFileFromNfs(src + 4, "/tmp/dd.img", loaderData)) {
            logMessage(ERROR, "unable to retrieve driver disk: %s", src);
            return;
        }
    } else if (!strncmp(src, "ftp://", 6) || !strncmp(src, "http://", 7)) {
        unlinkf = 1;
        if (getFileFromUrl(src, "/tmp/dd.img", loaderData)) {
            logMessage(ERROR, "unable to retrieve driver disk: %s", src);
            return;
        }
    /* FIXME: this is a hack so that you can load a driver disk from, eg, 
     * scsi cdrom drives */
#if !defined(__s390__) && !defined(__s390x__)
    } else if (!strncmp(src, "cdrom", 5)) {
        loadDriverDisks(CLASS_UNSPEC, loaderData);
        return;
#endif
    } else if (!strncmp(src, "path:", 5)) {
	path = src + 5;
    } else {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown driver disk kickstart source: %s"), src);
        return;
    }

    if (!mountLoopback(path, "/tmp/drivers", "loop6")) {
        loadFromLocation(loaderData, "/tmp/drivers");
        umountLoopback("/tmp/drivers", "loop6");
        unlink("/tmp/drivers");
        if (unlinkf) unlink(path);
    }

}

static void getDDFromDev(struct loaderData_s * loaderData, char * dev, 
                         char * fstype);

void useKickstartDD(struct loaderData_s * loaderData,
                    int argc, char ** argv) {
    char * fstype = NULL;
    char * dev = NULL;
    char * src = NULL;

    char * biospart = NULL, * p = NULL; 
    int usebiosdev = 0;

    poptContext optCon;
    int rc;
    struct poptOption ksDDOptions[] = {
        { "type", '\0', POPT_ARG_STRING, &fstype, 0, NULL, NULL },
        { "source", '\0', POPT_ARG_STRING, &src, 0, NULL, NULL },
        { "biospart", '\0', POPT_ARG_NONE, &usebiosdev, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };
    
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksDDOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("The following invalid argument was specified for "
                         "the kickstart driver disk command: %s:%s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    dev = (char *) poptGetArg(optCon);

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
        return getDDFromDev(loaderData, dev, fstype);
    } else {
        return getDDFromSource(loaderData, src);
    }
}

static void getDDFromDev(struct loaderData_s * loaderData, char * dev, 
                        char * fstype) {
    devMakeInode(dev, "/tmp/dddev");
    if (fstype) {
        if (doPwMount("/tmp/dddev", "/tmp/drivers", fstype, 
                      IMOUNT_RDONLY, NULL)) {
            logMessage(ERROR, "unable to mount %s as %s", dev, fstype);
            return;
        }
    } else if (doPwMount("/tmp/dddev", "/tmp/drivers", "vfat", IMOUNT_RDONLY, NULL)) {
        if (doPwMount("/tmp/dddev", "/tmp/drivers", "ext2", IMOUNT_RDONLY, NULL)) {
            if (doPwMount("/tmp/dddev", "/tmp/drivers", "iso9660", IMOUNT_RDONLY, NULL)) {
                logMessage(ERROR, "unable to mount driver disk %s", dev);
                return;
            }
        }
    }

    loadFromLocation(loaderData, "/tmp/drivers");
    umount("/tmp/drivers");
    unlink("/tmp/drivers");
    unlink("/tmp/dddev");
}
