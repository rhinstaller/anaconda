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

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
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

#include "../isys/imount.h"
#include "../isys/isys.h"


/* JKFIXME: this is a pile of crap... should at least only be done once */
/* Need to tell loop.h what the actual dev_t type is. */
#undef dev_t
#if defined(__alpha) || (defined(__sparc__) && defined(__arch64__))
#define dev_t unsigned int
#else
#if defined(__x86_64__)
#define dev_t unsigned long
#else
#define dev_t unsigned short
#endif
#endif
#include <linux/loop.h>
#undef dev_t
#define dev_t dev_t



int umountLoopback(char * mntpoint, char * device) {
    int loopfd;

    umount(mntpoint);

    logMessage("umounting loopback %s %s", mntpoint, device);

    devMakeInode(device, "/tmp/loop");
    loopfd = open("/tmp/loop", O_RDONLY);

    if (ioctl(loopfd, LOOP_CLR_FD, 0) < 0)
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

    targfd = open(fsystem, O_RDONLY);
    if (targfd < 0)
        logMessage("opening target filesystem %s failed", fsystem);

    devMakeInode(device, filename);
    loopfd = open(filename, O_RDONLY);
    logMessage("mntloop %s on %s as %s fd is %d", 
               device, mntpoint, fsystem, loopfd);

    if (ioctl(loopfd, LOOP_SET_FD, targfd)) {
        logMessage("LOOP_SET_FD failed: %s", strerror(errno));
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

    if (doPwMount(filename, mntpoint, "iso9660", 1,
                  0, NULL, NULL)) {
        if (doPwMount(filename, mntpoint, "ext2", 1,
                      0, NULL, NULL)) {
            if (doPwMount(filename, mntpoint, "cramfs", 1,
                          0, NULL, NULL)) {
            
                logMessage("failed to mount loop: %s", 
                           strerror(errno));
                return LOADER_ERROR;
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

    if (!(dir = opendir(dirName))) {
        newtWinMessage(_("Error"), _("OK"), 
                   _("Failed to read directory %s: %s"),
                   dirName, strerror(errno));
        return 0;
    }

    /* Walk through the directories looking for a Red Hat CD image. */
    errno = 0;
    while ((ent = readdir(dir))) {
        sprintf(isoImage, "%s/%s", dirName, ent->d_name);
        
        if (fileIsIso(isoImage)) {
            errno = 0;
            continue;
        }
        
        if (mountLoopback(isoImage, "/tmp/loopimage", "loop7")) {
            logMessage("failed to mount %s", isoImage);
            errno = 0;
            continue;
        }
        
        if (!access("/tmp/loopimage/RedHat/base/hdstg1.img", F_OK)) {
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

/* JKFIXME: needs implementing.  should be very similar to the cdrom version */
void queryIsoMediaCheck(char * isoDir, int flags) {
    return;
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
        if (ent->d_name[0] == '.') continue;

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
            if (fd < 0) {
                logMessage("failed to open %s: %s", filespec,
                           strerror(errno));
                return 1;
            } 
            outfd = open(filespec2, O_RDWR | O_TRUNC | O_CREAT, 0644);
            if (outfd < 0) {
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
    copyUpdatesImg("/mnt/source/RedHat/base/updates.img");
    return 0;
}


/* copies a second stage from fd to dest and mounts on mntpoint */
int copyFileAndLoopbackMount(int fd, char * dest, int flags,
                             char * device, char * mntpoint) {
    int rc;
    struct stat sb;

    rc = copyFileFd(fd, dest);
    stat(dest, &sb);
    logMessage("copied %d bytes to %s%s", sb.st_size, dest, 
	       (rc) ? " (incomplete)" : "");
    
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
