/*
 * cdinstall.c - code to set up cdrom installs
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
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/ioctl.h>
#include <unistd.h>

#if !defined(__s390__) && !defined(__s390x__)
#include <linux/cdrom.h>
#endif

#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "cdinstall.h"
#include "mediacheck.h"

#include "../isys/probe.h"
#include "../isys/imount.h"
#include "../isys/isys.h"

static int getISOStatusFromFD(int isofd, char *mediasum);

/* ejects the CD device the device node /tmp/cdrom points at */
void ejectCdrom(void) {
  int ejectfd;

  logMessage("ejecting /tmp/cdrom...");
  if ((ejectfd = open("/tmp/cdrom", O_RDONLY | O_NONBLOCK, 0)) >= 0) {
      if (ioctl(ejectfd, CDROMEJECT, 0))
        logMessage("eject failed %d ", errno);
      close(ejectfd);
  } else {
      logMessage("eject failed %d ", errno);
  }
}

/* get description of ISO image from stamp file */
char *getReleaseDescriptorFromIso(char *file) {
    DIR * dir;
    FILE *f;
    struct dirent * ent;
    struct stat sb;
    char *stampfile;
    char *descr;
    char tmpstr[1024];
    int  filetype;

    lstat(file, &sb);
    if (S_ISBLK(sb.st_mode)) {
	filetype = 1;
	if (doPwMount(file, "/tmp/testmnt",
		      "iso9660", 1, 0, NULL, NULL)) {
	    logMessage("Failed to mount device %s to get description", file);
	    return NULL;
	}
    } else if (S_ISREG(sb.st_mode)) {
	filetype = 2;
	if (mountLoopback(file, "/tmp/testmnt", "loop6")) {
	    logMessage("Failed to mount iso %s to get description", file);
	    return NULL;
	}
    } else {
	    logMessage("Unknown type of file %s to get description", file);
	    return NULL;
    }

    if (!(dir = opendir("/tmp/testmnt"))) {
	umount("/tmp/testmnt");
	if (filetype == 2)
	    umountLoopback("tmp/testmnt", "loop6");
	return NULL;
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
    if (stampfile) {
	snprintf(tmpstr, sizeof(tmpstr), "/tmp/testmnt/%s", stampfile);
	f = fopen(tmpstr, "r");
	if (f) {
	    char *tmpptr;

	    /* skip over time stamp line */
	    tmpptr = fgets(tmpstr, sizeof(tmpstr), f);
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
	umountLoopback("tmp/testmnt", "loop6");

    if (descr) {
	char *dupdescr;
	
	dupdescr = strdup(descr);
	dupdescr[strlen(dupdescr)-1] = '\0';
        return dupdescr;
    } else {
	return descr;
    }
}


/*
 * Given cd device cddriver, this function will attempt to check its internal checksum.
 *
 * JKFIXME: this ignores "location", which should be fixed */
static char * mediaCheckCdrom(char *cddriver) {
    int rc;
    int first;

    devMakeInode(cddriver, "/tmp/cdrom");

    first = 1;
    do {
	char *descr=NULL;
	/* if first time through, see if they want to eject the CD      */
	/* currently in the drive (most likely the CD they booted from) */
	/* and test a different disk.  Otherwise just test the disk in  */
	/* the drive since it was inserted in the previous pass through */
	/* this loop, so they want it tested.                           */
	if (first) {
	    first = 0;
	    rc = newtWinChoice(_("Media Check"), _("Test"), _("Eject CD"),
			       _("Choose \"%s\" to test the CD currently in "
				 "the drive, or \"%s\" to eject the CD and "
				 "insert another for testing."), _("Test"),
			       _("Eject CD"));

	    if (rc == 1) {
		descr = getReleaseDescriptorFromIso("/tmp/cdrom");
		mediaCheckFile("/tmp/cdrom", descr);
	    }

	} else {
	    descr = getReleaseDescriptorFromIso("/tmp/cdrom");
	    mediaCheckFile("/tmp/cdrom", descr);
	}

	if (descr)
	    free(descr);

	ejectCdrom();
	
	rc = newtWinChoice(_("Media Check"), _("Test"), _("Continue"),
			   _("If you would like to test additional media, "
			     "insert the next CD and press \"%s\". "
			     "You do not have to test all CDs, although "
			     "it is recommended you do so at least once.\n\n"
			     "To begin the installation process "
			     "insert CD #1 into the drive "
			     "and press \"%s\"."),
			   _("Test"), _("Continue"));

	if (rc == 2) {
	    unlink("/tmp/cdrom");
	    return NULL;
	} else {
	    continue;
	}
    } while (1);
    
    return NULL;
}

/* output an error message when CD in drive is not the correct one */
/* Used by mountCdromStage2()                                      */
static void wrongCDMessage(void) {
    char *buf = sdupprintf(_("The %s CD was not found "
			     "in any of your CDROM drives. Please insert "
			     "the %s CD and press %s to retry."), PRODUCTNAME,
			   PRODUCTNAME, _("OK"));
    newtWinMessage(_("Error"), _("OK"), buf, _("OK"));
    free(buf);
}

/* Attempts to get a proper CD #1 in the drive */
/* Is called after mediacheck is done so that we can proceed with the install */
/* During mediacheck we have to have CD umount'd so it can be ejected */
/*                                                                    */
/* JKFIXME: Assumes CD is mounted as /mnt/source                      */
static void mountCdromStage2(char *cddev) {
    int gotcd1=0;
    int rc;

    devMakeInode(cddev, "/tmp/cdrom");
    do {
	do {
	    if (doPwMount("/tmp/cdrom", "/mnt/source", 
			  "iso9660", 1, 0, NULL, NULL)) {
		ejectCdrom();
		wrongCDMessage();
	    } else {
		break;
	    }
	} while (1);
	
	rc = mountStage2("/mnt/source/RedHat/base/stage2.img");
	/* if we failed, umount /mnt/source and keep going */
	if (rc) {
	    umount("/mnt/source");
	    ejectCdrom();
	    wrongCDMessage();
	} else {
	    gotcd1 = 1;
	}
    } while (!gotcd1);
}

/* reads iso status from device cddriver */
static int getISOStatusFromCDROM(char *cddriver, char *mediasum) {
    int isofd;
    int isostatus;

    devMakeInode(cddriver, "/tmp/cdrom");
    isofd = open("/tmp/cdrom", O_RDONLY);
    if (isofd < 0) {
	logMessage("Could not check iso status: %s", strerror(errno));
	unlink("/tmp/cdrom");
	return 0;
    }

    isostatus = getISOStatusFromFD(isofd, mediasum);

    close(isofd);
    unlink("/tmp/cdrom");

    return isostatus;
}

/* get support status */
/* if returns 1 we found status, and mediasum will be checksum */
static int getISOStatusFromFD(int isofd, char *mediasum) {
    unsigned char tmpsum[33];
    int skipsectors, isostatus;
    long long isosize, pvd_offset;

    if (mediasum)
	mediasum[0] = '\0';

    if ((pvd_offset = parsepvd(isofd, tmpsum, &skipsectors, &isosize, &isostatus)) < 0) {
	logMessage("Could not parse pvd");
	return 0;
    }

    if (mediasum)
	strcpy(mediasum, tmpsum);

    return isostatus;
}

/* writes iso status info to file '/tmp/isoinfo' for later use */
static void writeISOStatus(int status, char *mediasum) {
    FILE *f;

    if (!(f = fopen("/tmp/isoinfo", "w")))
	return;

    fprintf(f, "ISOSTATUS=%d\n", status);
    fprintf(f, "MEDIASUM=%s\n", mediasum);

    fclose(f);

}

/* ask about doing media check */
/* JKFIXME: Assumes CD is mounted as /mnt/source                      */
static void queryCDMediaCheck(char *dev, int flags) {
  int rc;
  char mediasum[33];
  int isostatus;

  /* dont bother to test in automated installs */
  if (FL_KICKSTART(flags))
      return;

  /* see what status is */
  isostatus = getISOStatusFromCDROM(dev, mediasum);
  writeISOStatus(isostatus, mediasum);

  /* see if we should check image(s) */
  if (!isostatus || FL_MEDIACHECK(flags)) {
    
    startNewt(flags);
    rc = newtWinChoice(_("CD Found"), _("OK"),
		       _("Skip"), 
       _("To begin testing the CD media before installation press %s.\n\n"
	 "Choose %s to skip the media test and start the installation."), _("OK"), _("Skip"));

    if (rc != 2) {
      
      /* unmount CD now we've identified */
      /* a valid disc #1 is present */
      umountStage2();
      umount("/mnt/source");
      
      /* test CD(s) */
      mediaCheckCdrom(dev);
      
      /* remount stage2 from CD #1 and proceed */
      mountCdromStage2(dev);
    }
  }
}

/* set up a cdrom, nominally for installation 
 *
 * location: where to mount the cdrom at JKFIXME: ignored
 * flags: usual loader flags
 * interactive: whether or not to prompt about questions/errors (1 is yes)
 *
 * side effect: found cdrom is mounted as /mnt/source.  stage2 mounted
 * as /mnt/runtime.
 */
char * setupCdrom(char * location, 
                  struct knownDevices * kd, 
                  moduleInfoSet modInfo, 
                  moduleList modLoaded, 
                  moduleDeps modDeps, 
                  int flags,
                  int interactive) {
    int i, rc;
    int foundinvalid = 0;
    char * buf;

    /* JKFIXME: ASSERT -- we have a cdrom device when we get here */
    do {
        for (i = 0; i < kd->numKnown; i++) {
            if (kd->known[i].class != CLASS_CDROM) continue;

            logMessage("trying to mount device %s", kd->known[i].name);
            devMakeInode(kd->known[i].name, "/tmp/cdrom");
            if (!doPwMount("/tmp/cdrom", "/mnt/source", "iso9660", 1, 0, 
                           NULL, NULL)) {
                if (!access("/mnt/source/RedHat/base/stage2.img", R_OK)) {
                    rc = mountStage2("/mnt/source/RedHat/base/stage2.img");
                    /* if we failed, umount /mnt/source and keep going */
                    if (rc) {
                        umount("/mnt/source");
                        if (rc == -1) foundinvalid = 1;
                        continue;
                    }

                    /* do the media check */
                    queryCDMediaCheck(kd->known[i].name, flags);

                    buf = malloc(200);
                    sprintf(buf, "cdrom://%s/mnt/source", kd->known[i].name);
                    return buf;
                }
                unlink("/tmp/cdrom");
            } 
        } 

        if (interactive) {
            char * buf;
            if (foundinvalid)
                buf = sdupprintf(_("No %s CD was found which matches your "
                                   "boot media.  Please insert the %s CD "
                                   "and press %s to retry."), PRODUCTNAME,
                                 PRODUCTNAME, _("OK"));
            else
                buf = sdupprintf(_("The %s CD was not found in any of your "
                                   "CDROM drives. Please insert the %s CD "
                                   "and press %s to retry."), PRODUCTNAME,
                                 PRODUCTNAME, _("OK"));

            rc = newtWinChoice(_("CD Not Found"),
                               _("OK"), _("Back"), buf, _("OK"));
            free(buf);
            if (rc == 2) return NULL;
        } else {
            /* we can't ask them about it, so just return not found */
            return NULL;
        }
    } while (1);
    return NULL;
}

/* try to find a Red Hat CD non-interactively */
char * findRedHatCD(char * location, 
                    struct knownDevices * kd, 
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags) {
    return setupCdrom(location, kd, modInfo, modLoaded, modDeps, flags, 0);
}



/* look for a Red Hat CD and mount it.  if we have problems, ask */
char * mountCdromImage(struct installMethod * method,
                       char * location, struct knownDevices * kd,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags) {

    setupCdrom(location, kd, modInfo, modLoaded, *modDepsPtr, flags, 1);
}
