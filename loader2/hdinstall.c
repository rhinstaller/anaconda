/*
 * hdinstall.c - code to set up hard drive installs
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>

#include "driverdisk.h"
#include "hdinstall.h"
#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "mediacheck.h"

#include "../isys/probe.h"
#include "../isys/imount.h"
#include "../isys/isys.h"


/* see if this is a partition name or not */
int isPartitionName(char *pname) {

    /* if it doesnt start with a alpha its not one */
    if (!isalpha(*pname))
	return 0;

    /* if it has a '/' in it then treat it specially */
    if (strchr(pname, '/')) {
	/* assume its either a /dev/ida/ or /dev/cciss device */
	/* these have form of c?d?p? if its a partition */
	return strchr(pname, 'p') != NULL;
    } else {
	/* if it ends with a digit we're ok */
	return isdigit(pname[strlen(pname)-1]);
    }
}

/* return NULL terminated array of pointers to names of partitons in
 * /proc/partitions
 */
static char **getPartitionsList(void) {
    FILE *f;
    int numfound = 0;
    char **rc=NULL;

    f = fopen("/proc/partitions", "r");
    if (!f) {
	logMessage("getPartitionsList: could not open /proc/partitions");
	return NULL;
    }

    /* read through /proc/partitions and parse out partitions */
    while (1) {
	char *tmpptr, *pptr;
	char tmpstr[4096];

	tmpptr = fgets(tmpstr, sizeof(tmpstr), f);

	if (tmpptr) {
	    char *a, *b;
	    int toknum = 0;

	    a = tmpstr;
	    while (1) {
		b = strsep(&a, " \n");

		/* if no fields left abort */
		if (!b)
		    break;

		/* if field was empty means we hit another delimiter */
		if (!*b)
		    continue;

		/* make sure this is a valid partition line, should start */
		/* with a numeral */
		if (toknum == 0) {
		    if (!isdigit(*b))
			break;
		} else if (toknum == 2) {
		    /* if size is exactly 1 then ignore it as an extended */
		    if (!strcmp(b, "1"))
			break;
		} else if (toknum == 3) {
		    /* this should be the partition name */
		    /* now we need to see if this is the block device or */
		    /* actually a partition name                         */
		    if (!isPartitionName(b))
			break;

		    /* we found a partition! */
		    pptr = (char *) malloc(strlen(b) + 7);
		    sprintf(pptr, "/dev/%s", b);

		    if (!rc) {
			rc = (char **) malloc(2*sizeof(char *));
		        rc[0] = pptr;
			rc[1] = NULL;
		    } else {
			int idx;
			
			rc = (char **) realloc(rc, (numfound+2)*sizeof(char *));
			idx = 0;
			while (idx < numfound) {
			    if (strcmp(pptr, rc[idx]) < 0)
				break;

			    idx++;
			}

			/* move existing out of way if necessary */
			if (idx != numfound)
			    memmove(rc+idx+1, rc+idx, (numfound-idx)*sizeof(char *));

			rc[idx] = pptr;
			rc[numfound+1] = NULL;
		    }
		    numfound++;
		    break;
		}
		toknum++;
	    }
	} else {
	    break;
	}
    }

    fclose(f);

    return rc;
}

/* returns length of partitionlist */
int lenPartitionsList(char **list) {
    char **part;
    int  rc;

    for (rc = 0, part = list; *part; rc++, part++);

    return rc;
}

/* frees partition list */
void freePartitionsList(char **list) {
    char **part;

    if (!list)
	return;

    for (part = list; *part; part++)
	if (*part)
	    free(*part);

    free(list);
}

/* set to 0 and set ifdef around test code at bottom to test partitionList */
#if 1

/* pull in second stage image for hard drive install */
static int loadHDImages(char * prefix, char * dir, int flags, 
			   char * device, char * mntpoint) {
    int fd, rc;
    char * path;

    /*setupRamdisk();*/

    path = alloca(50 + strlen(prefix) + (dir ? strlen(dir) : 2));

    sprintf(path, "%s/%s/RedHat/base/hdstg2.img", prefix, dir ? dir : "");

    if ((fd = open(path, O_RDONLY)) < 0) {
	logMessage("failed to open %s: %s", path, strerror(errno));
	return 1;
    } 

    /* handle updates.img now before we copy stage2 over... this allows
     * us to keep our ramdisk size as small as possible */
    sprintf(path, "%s/%s/RedHat/base/updates.img", prefix, dir ? dir : "");
    copyUpdatesImg(path);

    rc = copyFileAndLoopbackMount(fd, "/tmp/ramfs/hdstg2.img", flags, 
				  device, mntpoint);
    close(fd);

    return rc;
}

/* given a partition device and directory, tries to mount hd install image */
static char * setupIsoImages(char * device, char * dirName,  int flags) {
    int rc;
    char * url;
    char filespec[1024];
    char * path;
    char *typetry[] = {"ext2", "vfat", NULL};
    char **type;

    logMessage("mounting device %s for hard drive install", device);

    if (!FL_TESTING(flags)) {
	/* +5 skips over /dev/ */
	if (devMakeInode(device, "/tmp/hddev"))
	    logMessage("devMakeInode failed!");

	/* XXX try to mount as ext2 and then vfat */
	for (type=typetry; *type; type++) {
	    if (!doPwMount("/tmp/hddev", "/tmp/hdimage", *type, 1, 0, NULL, NULL))
		break;
	}

	if (!type)
	    return NULL;

	sprintf(filespec, "/tmp/hdimage/%s", dirName);

	if ((path = validIsoImages(filespec))) {
	    char updpath[4096];

	    logMessage("Path to valid iso is %s", path);

	    snprintf(updpath, sizeof(updpath), "%s/updates.img", filespec);
	    logMessage("Looking for updates for HD in %s", updpath);
	    copyUpdatesImg(updpath);
	    
	    rc = mountLoopback(path, "/tmp/loopimage", "loop0");
	    if (!rc) {
		rc = loadHDImages("/tmp/loopimage", "/", flags, "loop1",
				  "/mnt/runtime");
		if (rc) {
		  newtWinMessage(_("Error"), _("OK"),
			_("An error occured reading the install "
			  "from the ISO images. Please check your ISO "
			  "images and try again."));
		} else {
		    queryIsoMediaCheck(path, flags);
		}
	    }
	    umountLoopback("/tmp/loopimage", "loop0");

	} else {
	    rc = 1;
	}

	umount("/tmp/hdimage");

	if (rc)
	    return NULL;
    } else {
	/* in test mode I dont know what to do - just pretend I guess */
	type = typetry;
    }
   
    url = malloc(50 + strlen(dirName ? dirName : ""));
    sprintf(url, "hd://%s:%s/%s", device, *type, dirName ? dirName : ".");

    return url;
}


/* setup hard drive based install from a partition with a filesystem and
 * ISO images on that filesystem
 */
char * mountHardDrive(struct installMethod * method,
		      char * location, struct knownDevices * kd,
		      struct loaderData_s * loaderData,
    		      moduleInfoSet modInfo, moduleList modLoaded,
		      moduleDeps * modDepsPtr, int flags) {
    int rc;
    int i;

    newtComponent listbox, label, dirEntry, form, okay, back, text;
    struct newtExitStruct es;
    newtGrid entryGrid, grid, buttons;

    int done = 0;
    char * dir = strdup("");
    char * tmpDir;
    char * url = NULL;
    char * buf;
    int numPartitions;

    char **partition_list;
    char *selpart;
    char *kspartition, *ksdirectory;

    logMessage("in mountHardDrive():");

    /* handle kickstart data first if available */
    if (loaderData->method &&
	!strncmp(loaderData->method, "hd", 2) &&
	loaderData->methodData) {
	
	kspartition = ((struct hdInstallData *)loaderData->methodData)->partition;
	ksdirectory = ((struct hdInstallData *)loaderData->methodData)->directory;
	logMessage("partition  is %s, dir is %s", kspartition, ksdirectory);

	/* if exist, duplicate */
	if (kspartition)
	    kspartition = strdup(kspartition);
	if (ksdirectory)
	    ksdirectory = strdup(ksdirectory);

	if (!kspartition || !ksdirectory) {
	    logMessage("missing partition or directory specification");
	    free(loaderData->method);
	    loaderData->method = NULL;
	} else {
	    url = setupIsoImages(kspartition, ksdirectory, flags);
	    if (!url) {
		logMessage("unable to find Red Hat installation images on hd");
		free(loaderData->method);
		loaderData->method = NULL;
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

	partition_list = getPartitionsList();
	numPartitions = lenPartitionsList(partition_list);

	logMessage("partitionslist: %d", numPartitions);
	for (i=0; i<numPartitions; i++)
	    logMessage("%s", partition_list[i]);

	/* no partitions found, try to load a device driver disk for storage */
	if (!numPartitions) {
	    rc = newtWinChoice(_("Hard Drives"), _("Yes"), _("Back"),
			    _("You don't seem to have any hard drives on "
			      "your system! Would you like to configure "
			      "additional devices?"));
	    if (rc == 2)
		return NULL;

            rc = loadDriverFromMedia(CLASS_HD, modLoaded, modDepsPtr, 
				     modInfo, kd, flags, 0);
            if (rc == LOADER_BACK)
		return NULL;

	    continue;
	}


	/* now find out which partition has the hard drive install images */
	buf = sdupprintf(_("What partition and directory on that "
			   "partition hold the CD (iso9660) images "
			   "for %s? If you don't see the disk drive "
			   "you're using listed here, press F2 "
			   "to configure additional devices."), PRODUCTNAME);
	text = newtTextboxReflowed(-1, -1, buf, 62, 5, 5, 0);
	free(buf);
	
	listbox = newtListbox(-1, -1, numPartitions > 5 ? 5 : numPartitions,
			      NEWT_FLAG_RETURNEXIT | 
			      (numPartitions > 5 ? NEWT_FLAG_SCROLL : 0));
	
	for (i = 0; i < numPartitions; i++)
	    newtListboxAppendEntry(listbox, partition_list[i], partition_list[i]);

	/* if we had ks data around use it to prime entry, then get rid of it*/
	if (kspartition) {
	    newtListboxSetCurrentByKey(listbox, kspartition);
	    free(kspartition);
	    kspartition = NULL;
	}

	label = newtLabel(-1, -1, _("Directory holding images:"));

	dirEntry = newtEntry(28, 11, dir, 28, &tmpDir, NEWT_ENTRY_SCROLL);

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
	    return NULL;
	} else if (es.reason == NEWT_EXIT_HOTKEY && es.u.key == NEWT_KEY_F2) {
            rc = loadDriverFromMedia(CLASS_HD, modLoaded, modDepsPtr, 
				     modInfo, kd, flags, 0);
            if (rc == LOADER_BACK)
		return NULL;

	    continue;
	}

	logMessage("partition %s selected", selpart);
	
	url = setupIsoImages(selpart + 5, dir, flags);
	if (!url) {
	    newtWinMessage(_("Error"), _("OK"), 
			_("Device %s does not appear to contain "
			  "Red Hat CDROM images."), selpart);
	    continue;
	}

	done = 1; 

	umount("/tmp/hdimage");
	rmdir("/tmp/hdimage");
    }

    free(dir);

    return url;
}

void setKickstartHD(struct loaderData_s * loaderData, int argc,
                     char ** argv, int * flagsPtr) {
    char *partition, *dir;
    poptContext optCon;
    int rc;
    struct poptOption ksHDOptions[] = {
        { "partition", '\0', POPT_ARG_STRING, &partition, 0 },
        { "dir", '\0', POPT_ARG_STRING, &dir, 0 },
        { 0, 0, 0, 0, 0 }
    };

    logMessage("kickstartFromHD");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksHDOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to HD kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    loaderData->method = strdup("hd");
    loaderData->methodData = calloc(sizeof(struct hdInstallData *), 1);
    if (partition)
        ((struct hdInstallData *)loaderData->methodData)->partition = partition;
    if (dir)
        ((struct hdInstallData *)loaderData->methodData)->directory = dir;

    logMessage("results of hd ks, partition is %s, dir is %s", partition, dir);
}

int kickstartFromHD(char *kssrc, int flags) {
    int rc;
    char *p, *q, *tmpstr, *ksdev, *kspath;

    logMessage("getting kickstart file from harddrive");

    /* format is ks=hd:[device]:/path/to/ks.cfg */
    /* split of pieces */
    tmpstr = strdup(kssrc);
    p = strchr(tmpstr, ':');
    if (p)
	q = strchr(p+1, ':');
    
    /* no second colon, assume its the old format of ks=hd:[device]/path/to/ks.cfg */
    /* this format is bad however because some devices have '/' in them! */
    if (!q)
	q = strchr(p+1, '/');

    if (!p || !q) {
	logMessage("Format of command line is ks=hd:[device]:/path/to/ks.cfg");
	free(tmpstr);
	return 1;
    }

    *q = '\0';
    ksdev = p+1;
    kspath = q+1;

    logMessage("Loading ks from device %s on path %s", ksdev, kspath);
    if ((rc=getKickstartFromBlockDevice(ksdev, kspath))) {
	if (rc == 3) {
	    startNewt(flags);
	    newtWinMessage(_("Error"), _("OK"),
			   _("Cannot find kickstart file on hard drive."));
	}
	return 1;
    }

    return 0;
}


#endif

/* use for testing */
#if 0
int main() {
    char **rc, **p;

    rc = getPartitionsList();

    printf("rc: %d\n", lenPartitionsList(rc));
    for (p=rc; *p; p++)
	printf("%s\n", *p);
    freePartitionsList(rc);
}
#endif
