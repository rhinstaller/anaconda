/*
 * method.c - generic install method setup functions
 *
 * Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <libgen.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <libgen.h>

#include "copy.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "mediacheck.h"
#include "method.h"

#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/cpio.h"
#include "../pyanaconda/isys/log.h"

#include "devt.h"

#include "nfsinstall.h"
#include "hdinstall.h"
#include "urlinstall.h"

/* boot flags */
extern uint64_t flags;

/* returns the *absolute* path (malloced) to the #1 iso image */
/* get timestamp and description of ISO image from stamp file */
/* returns 0 on success, -1 otherwise                         */
int readStampFileFromIso(char *file, char **timestamp, char **releasedescr) {
    DIR * dir;
    FILE *f;
    struct dirent * ent;
    struct stat sb;
    char *stampfile;
    char *descr, *tstamp;
    char tmpstr[1024];
    int  rc;

    lstat(file, &sb);
    if (S_ISBLK(sb.st_mode)) {
	if (doPwMount(file, "/tmp/testmnt", "iso9660", "ro", NULL)) {
	    logMessage(ERROR, "Failed to mount device %s to get description",
                       file);
	    return -1;
	}
    } else if (S_ISREG(sb.st_mode)) {
	if (doPwMount(file, "/tmp/testmnt", "auto", "ro", NULL)) {
	    logMessage(ERROR, "Failed to mount iso %s to get description",
                       file);
	    return -1;
	}
    } else {
	    logMessage(ERROR, "Unknown type of file %s to get description",
                       file);
	    return -1;
    }

    if (!(dir = opendir("/tmp/testmnt"))) {
	umount("/tmp/testmnt");
	return -1;
    }

    errno = 0;
    stampfile = NULL;
    while ((ent = readdir(dir))) {
	if (!strncmp(ent->d_name, ".discinfo", 9)) {
	    stampfile = strdup(".discinfo");
	    break;
	}
    }

    closedir(dir);
    descr = NULL;
    tstamp = NULL;
    if (stampfile) {
	snprintf(tmpstr, sizeof(tmpstr), "/tmp/testmnt/%s", stampfile);
	f = fopen(tmpstr, "r");
	if (f) {
	    char *tmpptr;

	    /* readtime stamp line */
	    tmpptr = fgets(tmpstr, sizeof(tmpstr), f);
	    
	    if (tmpptr)
		tstamp = strdup(tmpstr);

	    /* now read OS description line */
	    if (tmpptr)
		tmpptr = fgets(tmpstr, sizeof(tmpstr), f);

	    if (tmpptr)
		descr = strdup(tmpstr);

	    fclose(f);
	}
    }

    free(stampfile);

    umount("/tmp/testmnt");

    if (descr != NULL && tstamp != NULL) {
	descr[strlen(descr)-1] = '\0';
	*releasedescr = descr;

	tstamp[strlen(tstamp)-1] = '\0';
	*timestamp = tstamp;

	rc = 0;
    } else {
	rc = 1;
    }	

    return rc;
}

/* XXX this ignores "location", which should be fixed
 *
 * Given a starting isoFile, will offer choice to mediacheck it and
 * all other ISO images in the same directory with the same stamp
 */
void queryIsoMediaCheck(char *isoFile) {
    DIR * dir;
    struct dirent * ent;
    char *isoDir;
    char isoImage[1024];
    char tmpmessage[1024];
    char *master_timestamp;
    char *tmpstr;
    int rc, first;

    /* dont bother to test in automated installs */
    if (FL_KICKSTART(flags) && !FL_MEDIACHECK(flags))
	return;

    /* if they did not specify to mediacheck explicitely then return */
    if (!FL_MEDIACHECK(flags))
	return;

    /* check that file is actually an iso */
    if (!fileIsIso(isoFile))
	return;

    /* get stamp of isoFile, free descr since we dont care */
    readStampFileFromIso(isoFile, &master_timestamp, &tmpstr);
    free(tmpstr);
    
    /* get base path from isoFile */
    tmpstr = strdup(isoFile);
    isoDir = strdup(dirname(tmpstr));
    free(tmpstr);

    logMessage(DEBUGLVL, "isoFile = %s", isoFile);
    logMessage(DEBUGLVL, "isoDir  = %s", isoDir);
    logMessage(DEBUGLVL, "Master Timestemp = %s", master_timestamp);

    if (!(dir = opendir(isoDir))) {
	newtWinMessage(_("Error"), _("OK"), 
		       _("Failed to read directory %s: %m"),
		       isoDir);
	free(isoDir);
	free(master_timestamp);
	return;
    }

    /* Walk through the directories looking for a CD images. */
    errno = 0;
    first = 0;
    while (1) {
	char *nextname;
	char *tdescr, *tstamp;

	if (first) {
	    first = 1;
	    nextname = isoFile;
	} else {
	    ent = readdir(dir);
	    if (!ent)
		break;

	    nextname = ent->d_name;
	}

	/* synthesize name of iso from isoDir and file entry */
	snprintf(isoImage, sizeof(isoImage), "%s/%s", isoDir, nextname);

	/* see if this is an iso image */
	if (!fileIsIso(isoImage)) {
	    errno = 0;
	    continue;
	}

	/* see if its part of the current CD set */
	readStampFileFromIso(isoImage, &tstamp, &tdescr);
	if (strcmp(tstamp, master_timestamp)) {
	    errno = 0;
	    continue;
	}
	    
	/* found a valid candidate, proceed */
	snprintf(tmpmessage, sizeof(tmpmessage),
		 _("Would you like to perform a checksum "
		   "test of the ISO image:\n\n   %s?"), isoImage);

	rc = newtWinChoice(_("Checksum Test"), _("Test"), _("Skip"),
			   tmpmessage);

	if (rc == 2) {
	    logMessage(INFO, "mediacheck: skipped checking of %s", isoImage);
	    if (tdescr)
		free(tdescr);
	    continue;
	} else {
	    doMediaCheck(isoImage, tdescr);
	    if (tdescr)
		free(tdescr);

	    continue;
	}
    }

    free(isoDir);
    free(master_timestamp);
    closedir(dir);
}

static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

/* 
 * unpack a gzipped cpio ball into a tree rooted at rootDir
 * returns 0 on success, 1 on failure
 */
int unpackCpioBall(char * ballPath, char * rootDir) {
    gzFile fd;
    char *buf, *cwd;
    int rc = 1;

    if (access(ballPath, R_OK))
        return 1;

    if (access(rootDir, R_OK))
        mkdirChain(rootDir);

    buf = (char *)malloc(PATH_MAX);
    cwd = getcwd(buf, PATH_MAX);
    if ((rc = chdir(rootDir)) == 0) {
        fd = gunzip_open(ballPath);
        if (fd) {
            if (!installCpioFile(fd, NULL, NULL, 0)) {
                logMessage(INFO, "copied contents of %s into %s", ballPath,
                           rootDir);
                rc = chdir(cwd);
                return 0;
            }
            gunzip_close(fd);
        }
        rc = chdir(cwd);
    }

    return 1;
}

void copyUpdatesImg(char * path) {
    if (!access(path, R_OK)) {
        if (!doPwMount(path, "/tmp/update-disk", "auto", "ro", NULL)) {
            copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                          copyErrorFn);
            umount("/tmp/update-disk");
            unlink("/tmp/update-disk");
        } else {
            unpackCpioBall(path, "/tmp/updates");
        }
    }
}

void copyProductImg(char * path) {
    if (!access(path, R_OK)) {
        if (!doPwMount(path, "/tmp/product-disk", "auto", "ro", NULL)) {
            copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                          copyErrorFn);
            umount("/tmp/product-disk");
            unlink("/tmp/product-disk");
        }
    }
}

/* given a device name (w/o '/dev' on it), try to get a file */
/* Error codes: 
      1 - could not create device node
      2 - could not mount device as ext2, vfat, or iso9660
      3 - file named path not there
*/
int getFileFromBlockDevice(char *device, char *path, char * dest) {
    int rc, i;
    char file[4096];

    logMessage(INFO, "getFileFromBlockDevice(%s, %s)", device, path);

    /* some USB thumb drives and hard drives are slow to initialize */
    /* retry up to 5 times or 31 seconds */
    rc = doPwMount(device, "/tmp/mnt", "auto", "ro", NULL);
    for (i = 0; mountMightSucceedLater(rc) && i < 5; ++i) {
        logMessage(INFO, "sleeping to wait for USB storage devices");
        sleep(1 << i);
        rc = doPwMount(device, "/tmp/mnt", "auto", "ro", NULL);
        logMessage(ERROR, "error code: %d", rc);
    }
    if (rc) {
        logMessage(ERROR, "failed to mount /dev/%s: %m", device);
        return 2;
    }

    snprintf(file, sizeof(file), "/tmp/mnt/%s", path);
    logMessage(INFO, "Searching for file on path %s", file);
    
    if (access(file, R_OK)) {
	rc = 3;
    } else {
	copyFile(file, dest);
	rc = 0;
	logMessage(INFO, "file copied to %s", dest);
    }    

    umount("/tmp/mnt");
    unlink("/tmp/mnt");
    return rc;
}
