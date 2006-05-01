/*
 * method.c - generic install method setup functions
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
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

#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "mediacheck.h"
#include "method.h"

#include "../isys/imount.h"
#include "../isys/isys.h"

#include "devt.h"

#include "nfsinstall.h"
#include "hdinstall.h"
#include "urlinstall.h"

int umountLoopback(char * mntpoint, char * device) {
    int loopfd;

    umount(mntpoint);

    logMessage("umounting loopback %s %s", mntpoint, device);

    devMakeInode(device, "/tmp/loop");
    loopfd = open("/tmp/loop", O_RDONLY);

    if (ioctl(loopfd, LOOP_CLR_FD, 0) == -1)
        logMessage("LOOP_CLR_FD failed for %s %s (%s)", mntpoint, device, 
		   strerror(errno));

    close(loopfd);

    return 0;
}


int mountLoopback(char * fsystem, char * mntpoint, char * device) {
    struct loop_info loopInfo;
    int targfd, loopfd;
    char *filename;

    mkdirChain(mntpoint);
    filename = alloca(15 + strlen(device));
    sprintf(filename, "/tmp/%s", device);

    mkdirChain(mntpoint);

#ifdef O_DIRECT
    targfd = open(fsystem, O_RDONLY | O_DIRECT);
    if (targfd == -1) {
#endif
	targfd = open(fsystem, O_RDONLY);
	if (targfd == -1) {
	    logMessage("open file to loop mount %s failed", fsystem);
	    return LOADER_ERROR;
	}
#ifdef O_DIRECT
    }
#endif

    devMakeInode(device, filename);
    loopfd = open(filename, O_RDONLY);
    if (loopfd == -1) {
	logMessage("unable to open loop device %s", filename);
	return LOADER_ERROR;
    }
    logMessage("mntloop %s on %s as %s fd is %d", 
               device, mntpoint, fsystem, loopfd);

    if (ioctl(loopfd, LOOP_SET_FD, targfd)) {
        logMessage("LOOP_SET_FD failed: %s", strerror(errno));
        ioctl(loopfd, LOOP_CLR_FD, 0);
        close(targfd);
        close(loopfd);
        return LOADER_ERROR;
    }

    close(targfd);

    memset(&loopInfo, 0, sizeof(loopInfo));
    strcpy(loopInfo.lo_name, fsystem);

    if (ioctl(loopfd, LOOP_SET_STATUS, &loopInfo)) {
        logMessage("LOOP_SET_STATUS failed: %s", strerror(errno));
        close(loopfd);
        return LOADER_ERROR;
    }

    close(loopfd);

    /* FIXME: really, mountLoopback() should take a list of "valid" 
     * filesystems for the specific type of image being mounted */
    if (doPwMount(filename, mntpoint, "iso9660", 1,
                  0, NULL, NULL, 0, 0, NULL)) {
        if (doPwMount(filename, mntpoint, "ext2", 1,
                      0, NULL, NULL, 0, 0, NULL)) {
            if (doPwMount(filename, mntpoint, "cramfs", 1,
                          0, NULL, NULL, 0, 0, NULL)) {
              if (doPwMount(filename, mntpoint, "vfat", 1,
                            0, NULL, NULL, 0, 0, NULL)) {
                logMessage("failed to mount loop: %s", 
                           strerror(errno));
                loopfd = open(filename, O_RDONLY);
                ioctl(loopfd, LOOP_CLR_FD, 0);
                close(loopfd);
                return LOADER_ERROR;
              }
            }
        }
    }

    return 0;
}

/* returns the *absolute* path (malloced) to the #1 iso image */
char * validIsoImages(char * dirName) {
    DIR * dir;
    struct dirent * ent;
    char isoImage[1024];
    char path[1024];

    if (!(dir = opendir(dirName))) {
        newtWinMessage(_("Error"), _("OK"), 
                   _("Failed to read directory %s: %s"),
                   dirName, strerror(errno));
        return 0;
    }

    /* Walk through the directories looking for a Red Hat CD image. */
    errno = 0;
    while ((ent = readdir(dir))) {
        snprintf(isoImage, sizeof(isoImage), "%s/%s", dirName, ent->d_name);
        
        if (!fileIsIso(isoImage)) {
            errno = 0;
            continue;
        }
        
        if (mountLoopback(isoImage, "/tmp/loopimage", "loop7")) {
            logMessage("failed to mount %s", isoImage);
            errno = 0;
            continue;
        }
        
	snprintf(path, sizeof(path), "/tmp/loopimage/%s/base/hdstg2.img", getProductPath());
        if (!access(path, F_OK)) {
            umountLoopback("/tmp/loopimage", "loop7");
            break;
        }
        
        umountLoopback("/tmp/loopimage", "loop7");
        
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
	if (doPwMount(file, "/tmp/testmnt",
		      "iso9660", 1, 0, NULL, NULL, 0, 0, NULL)) {
	    logMessage("Failed to mount device %s to get description", file);
	    return -1;
	}
    } else if (S_ISREG(sb.st_mode)) {
	filetype = 2;
	if (mountLoopback(file, "/tmp/testmnt", "loop6")) {
	    logMessage("Failed to mount iso %s to get description", file);
	    return -1;
	}
    } else {
	    logMessage("Unknown type of file %s to get description", file);
	    return -1;
    }

    if (!(dir = opendir("/tmp/testmnt"))) {
	umount("/tmp/testmnt");
	if (filetype == 2)
	    umountLoopback("/tmp/testmnt", "loop6");
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
	umountLoopback("/tmp/testmnt", "loop6");

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
void queryIsoMediaCheck(char *isoFile, int flags) {
    DIR * dir;
    struct dirent * ent;
    char *isoDir;
    char isoImage[1024];
    char tmpmessage[1024];
    char *master_timestamp;
    char *tmpstr;
    int rc, first;

    /* dont bother to test in automated installs */
    if (FL_KICKSTART(flags))
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

    logMessage("isoFile = %s", isoFile);
    logMessage("isoDir  = %s", isoDir);
    logMessage("Master Timestemp = %s", master_timestamp);

    if (!(dir = opendir(isoDir))) {
	newtWinMessage(_("Error"), _("OK"), 
		       _("Failed to read directory %s: %s"),
		       isoDir, strerror(errno));
	free(isoDir);
	free(master_timestamp);
	return;
    }

    /* Walk through the directories looking for a Red Hat CD images. */
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
	    logMessage("mediacheck: skipped checking of %s", isoImage);
	    if (tdescr)
		free(tdescr);
	    continue;
	} else {
	    mediaCheckFile(isoImage, tdescr, 0);
	    if (tdescr)
		free(tdescr);

	    continue;
	}
    }

    free(isoDir);
    free(master_timestamp);
    closedir(dir);
    
}

/* Recursive */
int copyDirectory(char * from, char * to) {
    DIR * dir;
    struct dirent * ent;
    int fd, outfd;
    char buf[4096];
    int i;
    struct stat sb;
    char filespec[256];
    char filespec2[256];
    char link[1024];

    mkdir(to, 0755);

    if (!(dir = opendir(from))) {
        newtWinMessage(_("Error"), _("OK"),
                       _("Failed to read directory %s: %s"),
                       from, strerror(errno));
        return 1;
    }

    errno = 0;
    while ((ent = readdir(dir))) {
        /* we could lose .a this way, but at least, we lose less */
        if ((ent->d_name[0] == '.') && (strlen(ent->d_name) <= 2)) continue;

        sprintf(filespec, "%s/%s", from, ent->d_name);
        sprintf(filespec2, "%s/%s", to, ent->d_name);

        lstat(filespec, &sb);

        if (S_ISDIR(sb.st_mode)) {
            logMessage("recursively copying %s", filespec);
            if (copyDirectory(filespec, filespec2)) return 1;
        } else if (S_ISLNK(sb.st_mode)) {
            i = readlink(filespec, link, sizeof(link) - 1);
            link[i] = '\0';
            if (symlink(link, filespec2)) {
                logMessage("failed to symlink %s to %s: %s",
                    filespec2, link, strerror(errno));
            }
        } else {
            fd = open(filespec, O_RDONLY);
            if (fd == -1) {
                logMessage("failed to open %s: %s", filespec,
                           strerror(errno));
                return 1;
            } 
            outfd = open(filespec2, O_RDWR | O_TRUNC | O_CREAT, 0644);
            if (outfd == -1) {
                logMessage("failed to create %s: %s", filespec2,
                           strerror(errno));
            } else {
                fchmod(outfd, sb.st_mode & 07777);

                while ((i = read(fd, buf, sizeof(buf))) > 0)
                    write(outfd, buf, i);
                close(outfd);
            }

            close(fd);
        }

        errno = 0;
    }

    closedir(dir);

    return 0;
}


void copyUpdatesImg(char * path) {
    if (!access(path, R_OK)) {
        if (!mountLoopback(path, "/tmp/update-disk", "loop7")) {
            copyDirectory("/tmp/update-disk", "/tmp/updates");
            umountLoopback("/tmp/update-disk", "loop7");
            unlink("/tmp/update-disk");
        }
    }
}

void copyProductImg(char * path) {
    if (!access(path, R_OK)) {
        if (!mountLoopback(path, "/tmp/product-disk", "loop7")) {
            copyDirectory("/tmp/product-disk", "/tmp/product");
            umountLoopback("/tmp/product-disk", "loop7");
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
    char * p;

    stamp1 = alloca(13);
    stamp2 = alloca(13);

    /* grab the one from the initrd */
    f = fopen("/.buildstamp", "r");
    if (!f) {
        fail = 1;
    } else {
        fgets(stamp1, 13, f);
	fclose(f);

        /* and the runtime */
        p = sdupprintf("%s/.buildstamp", path);
        f = fopen(p, "r");
        free(p);
        if (!f) {
            fail = 1;
        } else {
            fgets(stamp2, 13, f);
	    fclose(f);

            if (strncmp(stamp1, stamp2, 12) != 0) {
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
    umount("/mnt/runtime");
    umountLoopback("/mnt/runtime", "loop0");
}


/* mount a second stage, verify the stamp file, copy updates 
 * Returns 0 on success, 1 on failure to mount, -1 on bad stamp */
int mountStage2(char * path) {
    char imgPath[1024];
    if (access(path, R_OK)) {
        return 1;
    }

    if (mountLoopback(path, "/mnt/runtime", "loop0")) {
        return 1;
    }

    if (!verifyStamp("/mnt/runtime")) {
        umountLoopback("/mnt/runtime", "loop0");
        return -1;
    }

    /* JKFIXME: this is kind of silly.. /mnt/source is hardcoded :/ */
    snprintf(imgPath, sizeof(imgPath), "/mnt/source/%s/base/updates.img", getProductPath());
    copyUpdatesImg(imgPath);

    /* more hard coding */
    snprintf(imgPath, sizeof(imgPath), "/mnt/source/%s/base/product.img", getProductPath());
    copyProductImg(imgPath);

    return 0;
}


/* copies a second stage from fd to dest and mounts on mntpoint */
int copyFileAndLoopbackMount(int fd, char * dest, int flags,
                             char * device, char * mntpoint) {
    int rc;
    struct stat sb;

    rc = copyFileFd(fd, dest);
    stat(dest, &sb);
    logMessage("copied %" PRId64 " bytes to %s (%s)", sb.st_size, dest, 
               ((rc) ? " incomplete" : "complete"));
    
    if (rc) {
	/* just to make sure */
	unlink(dest);
	return 1;
    }

    if (mountLoopback(dest, mntpoint, device)) {
        /* JKFIXME: this used to be fatal, but that seems unfriendly */
        logMessage("Error mounting /dev/%s on %s (%s)", device, mntpoint, 
                   strerror(errno));
        unlink(dest);
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

    logMessage("getFileFromBlockDevice(%s, %s)", device, path);

    if (devMakeInode(device, "/tmp/srcdev"))
        return 1;

    if ((doPwMount("/tmp/srcdev", "/tmp/mnt", "vfat", 1, 0, NULL, NULL, 0, 0, NULL)) && 
        doPwMount("/tmp/srcdev", "/tmp/mnt", "ext2", 1, 0, NULL, NULL, 0, 0, NULL) && 
        doPwMount("/tmp/srcdev", "/tmp/mnt", "iso9660", 1, 0, NULL, NULL, 0, 0, NULL)) {
        logMessage("failed to mount /dev/%s: %s", device, strerror(errno));
        return 2;
    }

    snprintf(file, sizeof(file), "/tmp/mnt/%s", path);
    logMessage("Searching for file on path %s", file);
    
    if (access(file, R_OK)) {
	rc = 3;
    } else {
	copyFile(file, dest);
	rc = 0;
	logMessage("file copied to %s", dest);
    }    

    umount("/tmp/mnt");
    unlink("/tmp/mnt");
    unlink("/tmp/srcdev");
    return rc;
}

void setMethodFromCmdline(char * arg, struct loaderData_s * ld) {
    char * c, * dup;

    dup = strdup(arg);
    c = dup;
    /* : will let us delimit real information on the method */
    if ((c = strtok(c, ":"))) {
        c = strtok(NULL, ":");
 
        if (!strncmp(arg, "nfs:", 4)) {
	    ld->method = strdup("nfs");
            ld->methodData = calloc(sizeof(struct nfsInstallData *), 1);
            ((struct nfsInstallData *)ld->methodData)->host = strdup(c);
            if ((c = strtok(NULL, ":"))) {
                ((struct nfsInstallData *)ld->methodData)->directory = strdup(c);
            }
        } else if (!strncmp(arg, "ftp:", 4) || 
                   !strncmp(arg, "http:", 5)) {
	    ld->method = strcmp(arg, "ftp") ? strdup("ftp") : strdup("http");
            ld->methodData = calloc(sizeof(struct urlInstallData *), 1);
            ((struct urlInstallData *)ld->methodData)->url = strdup(arg);
        } else if (!strncmp(arg, "cdrom:", 6)) {
	    ld->method = strdup("cdrom");
        } else if (!strncmp(arg, "harddrive:", 10) ||
                   !strncmp(arg, "hd:", 3)) {
	    ld->method = strdup("hd");
            ld->methodData = calloc(sizeof(struct hdInstallData *), 1);
            ((struct hdInstallData *)ld->methodData)->partition = strdup(c);
            if ((c = strtok(NULL, ":"))) {
                ((struct hdInstallData *)ld->methodData)->directory = strdup(c);
            }
        }
    }
    free(dup);
    
}
