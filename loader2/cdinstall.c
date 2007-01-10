/*
 * cdinstall.c - code to set up cdrom installs
 *
 * Erik Troan <ewt@redhat.com>
 * Matt Wilson <msw@redhat.com>
 * Michael Fulbright <msf@redhat.com>
 * Jeremy Katz <katzj@redhat.com>
 *
 * Copyright 1997 - 2003 Red Hat, Inc.
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
#include <asm/types.h>
#include <linux/cdrom.h>

#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "log.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "cdinstall.h"
#include "mediacheck.h"

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
	char *descr;
	char *tstamp;
	int ejectcd;

	/* init every pass */
	ejectcd = 0;
	descr = NULL;

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

	    if (rc == 2)
		ejectcd = 1;
	}

	if (!ejectcd) {
	    /* XXX MSFFIXME: should check return code for error */
	    readStampFileFromIso("/tmp/cdrom", &tstamp, &descr);
	    mediaCheckFile("/tmp/cdrom", descr, 1);

	    if (descr)
		free(descr);
	}

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
			     "the %s CD and press %s to retry."), getProductName(),
			   getProductName(), _("OK"));
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
    char path[1024];

    devMakeInode(cddev, "/tmp/cdrom");
    do {
	do {
	    if (doPwMount("/tmp/cdrom", "/mnt/source", 
			  "iso9660", 1, 0, NULL, NULL, 0, 0, NULL)) {
		ejectCdrom();
		wrongCDMessage();
	    } else {
		break;
	    }
	} while (1);

	snprintf(path, sizeof(path), "/mnt/source/%s/base/stage2.img", getProductPath());
	rc = mountStage2(path);

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
  /* in rescue mode only test if they explicitly asked to */
  if ((!isostatus && !FL_RESCUE(flags)) || FL_MEDIACHECK(flags)) {
    
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
 * loaderData is the kickstart info, can be NULL meaning no info
 *
 * requirepkgs=1 means CD should have packages, otherwise we just find stage2
 *
 * side effect: found cdrom is mounted as /mnt/source.  stage2 mounted
 * as /mnt/runtime.
 */
char * setupCdrom(char * location, 
		  struct loaderData_s * loaderData,
                  moduleInfoSet modInfo, 
                  moduleList modLoaded, 
                  moduleDeps modDeps, 
                  int flags,
                  int interactive, 
		  int requirepkgs) {
    int i, rc;
    int foundinvalid = 0;
    int stage2inram = 0;
    char * buf;
    char *stage2img;
    struct device ** devices = NULL;

    devices = probeDevices(CLASS_CDROM, BUS_UNSPEC, 0);
    if (!devices) {
        logMessage("got to setupCdrom without a CD device");
        return NULL;
    }

    /* JKFIXME: ASSERT -- we have a cdrom device when we get here */
    do {
        for (i = 0; devices[i]; i++) {
	    if (!devices[i]->device) continue;
            logMessage("trying to mount CD device %s", devices[i]->device);
            devMakeInode(devices[i]->device, "/tmp/cdrom");
            if (!doPwMount("/tmp/cdrom", "/mnt/source", "iso9660", 1, 0, 
                           NULL, NULL, 0, 0, NULL)) {
		char path[1024];

		snprintf(path, sizeof(path), "/mnt/source/%s/base/stage2.img", getProductPath()); 
                if (!access(path, R_OK) &&
		    (!requirepkgs || !access("/mnt/source/.discinfo", R_OK))) {


		    /* if in rescue mode lets copy stage 2 into RAM so we can */
		    /* free up the CD drive and user can have it avaiable to  */
		    /* aid system recovery.                                   */
		    if (FL_RESCUE(flags) && totalMemory() > 128000) {
		        snprintf(path, sizeof(path), "/mnt/source/%s/base/stage2.img", getProductPath());
			rc = copyFile(path, "/tmp/ramfs/stage2.img");
			stage2img = "/tmp/ramfs/stage2.img";
			stage2inram = 1;
		    } else {
			snprintf(path, sizeof(path), "/mnt/source/%s/base/stage2.img", getProductPath());
			stage2img = strdup(path);
			stage2inram = 0;
		    }
	
		    rc = mountStage2(stage2img);

                    /* if we failed, umount /mnt/source and keep going */
                    if (rc) {
                        umount("/mnt/source");
                        if (rc == -1) foundinvalid = 1;
                        continue;
                    }

                    /* do the media check */
                    queryCDMediaCheck(devices[i]->device, flags);

		    /* if in rescue mode and we copied stage2 to RAM */
		    /* we can now unmount the CD                     */
		    if (FL_RESCUE(flags) && stage2inram) {
			umount("/mnt/source");
			unlink("/tmp/cdrom");
		    }

                    buf = malloc(200);
                    sprintf(buf, "cdrom://%s:/mnt/source", devices[i]->device);
                    return buf;
                }

		/* this wasnt the CD we were looking for, clean up and */
		/* try the next CD drive                               */
		umount("/mnt/source");
                unlink("/tmp/cdrom");
            } 
        } 

        if (interactive) {
            char * buf;
            if (foundinvalid)
                buf = sdupprintf(_("No %s CD was found which matches your "
                                   "boot media.  Please insert the %s CD "
                                   "and press %s to retry."), getProductName(),
                                 getProductName(), _("OK"));
            else
                buf = sdupprintf(_("The %s CD was not found in any of your "
                                   "CDROM drives. Please insert the %s CD "
                                   "and press %s to retry."), getProductName(),
                                 getProductName(), _("OK"));

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
                    moduleInfoSet modInfo, 
                    moduleList modLoaded, 
                    moduleDeps modDeps, 
                    int flags,
		    int requirepkgs) {
    return setupCdrom(location, NULL, modInfo, modLoaded, modDeps, flags, 0, requirepkgs);
}



/* look for a Red Hat CD and mount it.  if we have problems, ask */
char * mountCdromImage(struct installMethod * method,
                       char * location, struct loaderData_s * loaderData,
                       moduleInfoSet modInfo, moduleList modLoaded,
                       moduleDeps * modDepsPtr, int flags) {

    return setupCdrom(location, loaderData, modInfo, modLoaded, *modDepsPtr, flags, 1, 1);
}

void setKickstartCD(struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr) {

    logMessage("kickstartFromCD");

    loaderData->method = strdup("cdrom");
}

int kickstartFromCD(char *kssrc, int flags) {
    int rc, i;
    char *p, *kspath;
    struct device ** devices;

    logMessage("getting kickstart file from first CDROM");

    devices = probeDevices(CLASS_CDROM, BUS_UNSPEC, 0);
    if (!devices) {
	logMessage("No CDROM devices found!");
	return 1;
    }

    /* format is ks=cdrom:[/path/to/ks.cfg] */
    kspath = "";
    p = strchr(kssrc, ':');
    if (p)
	kspath = p + 1;

    if (!p || strlen(kspath) < 1)
	kspath = "/ks.cfg";

    for (i=0; devices[i]; i++) {
        if (!devices[i]->device)
            continue;

        rc = getKickstartFromBlockDevice(devices[i]->device, kspath);
        if (rc == 0)
            return 0;
    }

    startNewt(flags);
    newtWinMessage(_("Error"), _("OK"),
                   _("Cannot find kickstart file on CDROM."));
    return 1;
}
