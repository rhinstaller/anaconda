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
#include <sys/types.h>
#include <unistd.h>
#include <libgen.h>

#include "copy.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "mediacheck.h"
#include "method.h"

#include "../isys/imount.h"
#include "../isys/isys.h"
#include "../isys/cpio.h"

#include "devt.h"

#include "nfsinstall.h"
#include "hdinstall.h"
#include "urlinstall.h"

/* boot flags */
extern uint64_t flags;

int umountLoopback(char * mntpoint, char * device) {
    int loopfd;

    umount(mntpoint);

    logMessage(INFO, "umounting loopback %s %s", mntpoint, device);

    loopfd = open(device, O_RDONLY);

    if (ioctl(loopfd, LOOP_CLR_FD, 0) == -1)
        logMessage(ERROR, "LOOP_CLR_FD failed for %s %s (%s)", mntpoint,
                   device, strerror(errno));

    close(loopfd);

    return 0;
}

int mountLoopback(char *fsystem, char *mntpoint, char *device) {
    char *opts;
    int rc;

    if (device == NULL) {
        logMessage(ERROR, "no loopback device given");
        return LOADER_ERROR;
    }

    if (access(fsystem, F_OK) != 0) {
       logMessage(ERROR, "file %s is not accessible", fsystem);
       return LOADER_ERROR;
    }

    rc = asprintf(&opts, "ro,loop=%s", device);
    if (doPwMount(fsystem, mntpoint, "iso9660", opts)) {
        if (doPwMount(fsystem, mntpoint, "ext2", opts)) {
            if (doPwMount(fsystem, mntpoint, "squashfs", opts)) {
                if (doPwMount(fsystem, mntpoint, "cramfs", opts)) {
                    if (doPwMount(fsystem, mntpoint, "vfat", opts)) {
                        logMessage(ERROR, "failed to mount loopback device %s on %s as %s: %s",
                                   device, mntpoint, fsystem, strerror(errno));
                        return LOADER_ERROR;
                    }
                }
            }
        }
    }

    logMessage(INFO, "mounted loopback device %s on %s as %s", mntpoint, device, fsystem);

    return 0;
}

/* returns the *absolute* path (malloced) to the #1 iso image */
char * validIsoImages(char * dirName, int *foundinvalid, int checkStage2) {
    DIR * dir;
    struct dirent * ent;
    char isoImage[1024];

    if (!(dir = opendir(dirName))) {
        newtWinMessage(_("Error"), _("OK"), 
                   _("Failed to read directory %s: %s"),
                   dirName, strerror(errno));
        return 0;
    }

    /* Walk through the directories looking for a CD image. */
    errno = 0;
    while ((ent = readdir(dir))) {
        if (*ent->d_name == '/')
           snprintf(isoImage, sizeof(isoImage), "%s%s", dirName, ent->d_name);
        else
           snprintf(isoImage, sizeof(isoImage), "%s/%s", dirName, ent->d_name);

        if (!fileIsIso(isoImage)) {
            errno = 0;
            continue;
        }

        if (mountLoopback(isoImage, "/tmp/loopimage", "/dev/loop7")) {
            logMessage(WARNING, "failed to mount %s", isoImage);
            errno = 0;
            continue;
        }

        if (!checkStage2) {
           umountLoopback("/tmp/loopimage", "/dev/loop7");
           break;
        }

	if (mountLoopback("/tmp/loopimage/images/stage2.img", "/mnt/runtime", "/dev/loop0")) {
	    umountLoopback("/mnt/runtime", "/dev/loop0");
	} else {
	    if (verifyStamp("/mnt/runtime")) {
		umountLoopback("/mnt/runtime", "/dev/loop0");
		umountLoopback("/tmp/loopimage", "/dev/loop7");
		break;
	    }
	    logMessage(ERROR, "disc %s is not the right image", isoImage);
	    umountLoopback("/mnt/runtime", "/dev/loop0");
	    if (foundinvalid) *foundinvalid = 1;
	}
        
        umountLoopback("/tmp/loopimage", "/dev/loop7");
        
        errno = 0;
    }
    
    closedir(dir);

    if (!ent) return NULL;

    return strdup(isoImage);
}

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
    int  filetype;
    int  rc;

    lstat(file, &sb);
    if (S_ISBLK(sb.st_mode)) {
	filetype = 1;
	if (doPwMount(file, "/tmp/testmnt", "iso9660", "ro")) {
	    logMessage(ERROR, "Failed to mount device %s to get description",
                       file);
	    return -1;
	}
    } else if (S_ISREG(sb.st_mode)) {
	filetype = 2;
	if (mountLoopback(file, "/tmp/testmnt", "/dev/loop6")) {
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
	if (filetype == 2)
	    umountLoopback("/tmp/testmnt", "/dev/loop6");
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

	    /* skip over arch */
	    if (tmpptr)
		tmpptr = fgets(tmpstr, sizeof(tmpstr), f);

	    /* now get the CD number */
	    if (tmpptr) {
		unsigned int len;
		char *p, *newstr;

		tmpptr = fgets(tmpstr, sizeof(tmpstr), f);
		
		/* nuke newline from end of descr, stick number on end*/
		for (p=descr+strlen(descr); p != descr && !isspace(*p); p--);

		*p = '\0';
		len = strlen(descr) + strlen(tmpstr) + 10;
		newstr = malloc(len);
		strncpy(newstr, descr, len-1);
		strncat(newstr, " ", len-1);

		/* is this a DVD or not?  If disc id has commas, like */
		/* "1,2,3", its a DVD                                 */
		if (strchr(tmpstr, ','))
		    strncat(newstr, "DVD\n", len-1);
		else {
		    strncat(newstr, "disc ", len-1);
		    strncat(newstr, tmpstr, len-1);
		}

		free(descr);
		descr = newstr;
	    }

	    fclose(f);
	}
    }

    free(stampfile);

    umount("/tmp/testmnt");
    if (filetype == 2)
	umountLoopback("/tmp/testmnt", "/dev/loop6");

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
		       _("Failed to read directory %s: %s"),
		       isoDir, strerror(errno));
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
        if (!mountLoopback(path, "/tmp/update-disk", "/dev/loop7")) {
            copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                          copyErrorFn);
            umountLoopback("/tmp/update-disk", "/dev/loop7");
            unlink("/tmp/update-disk");
        } else {
            unpackCpioBall(path, "/tmp/updates");
        }
    }
}

void copyProductImg(char * path) {
    if (!access(path, R_OK)) {
        if (!mountLoopback(path, "/tmp/product-disk", "/dev/loop7")) {
            copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                          copyErrorFn);
            umountLoopback("/tmp/product-disk", "/dev/loop7");
            unlink("/tmp/product-disk");
        }
    }
}


/* verify that the stamp files in / of the initrd and the stage2 match */
int verifyStamp(char * path) {
    char *stamp1;
    char *stamp2;
    FILE *f;
    int fail = 0;
    int i;
    char * p, *q;

    stamp1 = alloca(80);
    stamp2 = alloca(80);

    /* grab the one from the initrd */
    f = fopen("/.buildstamp", "r");
    if (!f) {
        fail = 1;
    } else {
        q = fgets(stamp1, 80, f);
	fclose(f);

        /* and the runtime */
        i = asprintf(&p, "%s/.buildstamp", path);
        f = fopen(p, "r");
        free(p);
        if (!f) {
            fail = 1;
        } else {
            q = fgets(stamp2, 80, f);
	    fclose(f);

            if (strcmp(stamp1, stamp2) != 0) {
                fail = 1;
            }
        }
    }

    if (fail == 1) {
        return 0;
    } else {
        return 1;
    }
}

/* unmount a second stage, if mounted. Used for CDs and mediacheck mostly,
   so we can eject CDs.                                                   */
void umountStage2(void) {
    umountLoopback("/mnt/runtime", "/dev/loop0");
}

/* mount a second stage, verify the stamp file, copy updates 
 * Returns 0 on success, 1 on failure to mount, -1 on bad stamp */
int mountStage2(char *stage2path) {
    if (access(stage2path, R_OK)) {
        return 1;
    }

    if (mountLoopback(stage2path, "/mnt/runtime", "/dev/loop0")) {
        return 1;
    }

    if (!verifyStamp("/mnt/runtime")) {
        umountLoopback("/mnt/runtime", "/dev/loop0");
        return -1;
    }

    return 0;
}


/* copies a second stage from fd to dest and mounts on mntpoint */
int copyFileAndLoopbackMount(int fd, char * dest,
                             char * device, char * mntpoint) {
    int rc;
    struct stat sb;

    rc = copyFileFd(fd, dest);
    stat(dest, &sb);
    logMessage(DEBUGLVL, "copied %" PRId64 " bytes to %s (%s)", sb.st_size, dest, 
               ((rc) ? " incomplete" : "complete"));
    
    if (rc) {
	/* just to make sure */
	unlink(dest);
	return 1;
    }

    if (mountLoopback(dest, mntpoint, device)) {
        /* JKFIXME: this used to be fatal, but that seems unfriendly */
        logMessage(ERROR, "Error mounting %s on %s (%s)", device,
                   mntpoint, strerror(errno));
        return 1;
    }

    return 0;
}

/* given a device name (w/o '/dev' on it), try to get a file */
/* Error codes: 
      1 - could not create device node
      2 - could not mount device as ext2, vfat, or iso9660
      3 - file named path not there
*/
int getFileFromBlockDevice(char *device, char *path, char * dest) {
    int rc;
    char file[4096];

    logMessage(INFO, "getFileFromBlockDevice(%s, %s)", device, path);

    if (doPwMount(device, "/tmp/mnt", "vfat", "ro") &&
        doPwMount(device, "/tmp/mnt", "ext2", "ro") && 
        doPwMount(device, "/tmp/mnt", "iso9660", "ro")) {
        logMessage(ERROR, "failed to mount /dev/%s: %s", device,
                   strerror(errno));
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

void setStage2LocFromCmdline(char * arg, struct loaderData_s * ld) {
    char * c, * dup;

    dup = strdup(arg);
    c = dup;
    /* : will let us delimit real information on the method */
    if ((c = strtok(c, ":"))) {
        c = strtok(NULL, ":");

        if (!strncmp(arg, "nfs:", 4)) {
            ld->method = METHOD_NFS;
            ld->stage2Data = calloc(sizeof(struct nfsInstallData *), 1);

            ((struct nfsInstallData *)ld->stage2Data)->mountOpts = NULL;
            ((struct nfsInstallData *)ld->stage2Data)->host = strdup(c);
            if ((c = strtok(NULL, ":"))) {
                ((struct nfsInstallData *)ld->stage2Data)->directory = strdup(c);
            }
        } else if (!strncmp(arg, "ftp:", 4) || 
                   !strncmp(arg, "http:", 5)) {
            ld->method = METHOD_URL;
            ld->stage2Data = calloc(sizeof(struct urlInstallData *), 1);
            ((struct urlInstallData *)ld->stage2Data)->url = strdup(arg);
#if !defined(__s390__) && !defined(__s390x__)
        } else if (!strncmp(arg, "cdrom:", 6)) {
            ld->method = METHOD_CDROM;
#endif
        } else if (!strncmp(arg, "harddrive:", 10) ||
                   !strncmp(arg, "hd:", 3)) {
            ld->method = METHOD_HD;
            ld->stage2Data = calloc(sizeof(struct hdInstallData *), 1);
            ((struct hdInstallData *)ld->stage2Data)->partition = strdup(c);
            if ((c = strtok(NULL, ":"))) {
                ((struct hdInstallData *)ld->stage2Data)->directory = strdup(c);
            }
        }
    }
    free(dup);
}
