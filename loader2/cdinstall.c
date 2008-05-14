/*
 * cdinstall.c - code to set up cdrom installs
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
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
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
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

/* boot flags */
extern uint64_t flags;

/* ejects the CD device the device node /tmp/cdrom points at */
void ejectCdrom(char *device) {
    int ejectfd;

    if (!device) return;
    logMessage(INFO, "ejecting %s...",device);
    if ((ejectfd = open(device, O_RDONLY | O_NONBLOCK, 0)) >= 0) {
        if (ioctl(ejectfd, CDROMEJECT, 0))
            logMessage(ERROR, "eject failed %d ", errno);
        close(ejectfd);
    } else {
        logMessage(ERROR, "eject failed %d ", errno);
    }
}

/*
 * Given cd device cddriver, this function will attempt to check its internal
 * checksum.
 *
 * JKFIXME: this ignores "location", which should be fixed */
static char * mediaCheckCdrom(char *cddriver) {
    int rc;
    int first;

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
            rc = newtWinChoice(_("Media Check"), _("Test"), _("Eject Disc"),
                               _("Choose \"%s\" to test the disc currently in "
                                 "the drive, or \"%s\" to eject the disc and "
                                 "insert another for testing."), _("Test"),
                               _("Eject Disc"));

            if (rc == 2)
                ejectcd = 1;
        }

        if (!ejectcd) {
            /* XXX MSFFIXME: should check return code for error */
            readStampFileFromIso(cddriver, &tstamp, &descr);
            doMediaCheck(cddriver, descr);

            if (descr)
                free(descr);
        }

        ejectCdrom(cddriver);

        rc = newtWinChoice(_("Media Check"), _("Test"), _("Continue"),
                       _("If you would like to test additional media, "
                       "insert the next disc and press \"%s\". "
                       "Testing each disc is not strictly required, however "
                       "it is highly recommended.  Minimally, the discs should "
                       "be tested prior to using them for the first time. "
                       "After they have been successfully tested, it is not "
                       "required to retest each disc prior to using it again."),
                       _("Test"), _("Continue"));

        if (rc == 2) {
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
    char *buf = NULL;
    int i;
    i = asprintf(&buf, (_("The %s disc was not found "
                          "in any of your drives. Please insert "
                          "the %s disc and press %s to retry."),
                getProductName(), getProductName(), _("OK")));
    newtWinMessage(_("Error"), _("OK"), buf);
    free(buf);
}

/* Attempts to get a proper CD #1 in the drive */
/* Is called after mediacheck is done so that we can proceed with the install */
/* During mediacheck we have to have CD umount'd so it can be ejected */
/*                                                                    */
static void mountCdromStage2(char *cddev, char *location) {
    int gotcd1=0;
    int rc;
    char *stage2loc;

    rc = asprintf(&stage2loc, "%s/images/stage2.img", location);

    do {
        do {
            if (doPwMount(cddev, location, "iso9660", "ro")) {
                ejectCdrom(cddev);
                wrongCDMessage();
            } else {
                break;
            }
        } while (1);

        rc = mountStage2(stage2loc);

        /* if we failed, umount location (usually) /mnt/source and keep going */
        if (rc) {
            umount(location);
            ejectCdrom(cddev);
            wrongCDMessage();
        } else {
            gotcd1 = 1;
        }
    } while (!gotcd1);

    free(stage2loc);
}

/* ask about doing media check */
static void queryCDMediaCheck(char *dev, char *location) {
    int rc;

    /* dont bother to test in automated installs */
    if (FL_KICKSTART(flags) && !FL_MEDIACHECK(flags))
        return;

    /* see if we should check image(s) */
    /* in rescue mode only test if they explicitly asked to */
    if (!FL_RESCUE(flags) || FL_MEDIACHECK(flags)) {
        startNewt();
        rc = newtWinChoice(_("Disc Found"), _("OK"), _("Skip"), 
             _("To begin testing the media before installation press %s.\n\n"
               "Choose %s to skip the media test and start the installation."),
             _("OK"), _("Skip"));

        if (rc != 2) {
            /* unmount CD now we've identified */
            /* a valid disc #1 is present */
            umountStage2();
            umount(location);

            /* test CD(s) */
            mediaCheckCdrom(dev);

            /* remount stage2 from CD #1 and proceed */
            mountCdromStage2(dev, location);
        }
    }
}

/* set up a cdrom, nominally for installation 
 *
 * location: where to mount the cdrom at
 * interactive: whether or not to prompt about questions/errors (1 is yes)
 *
 * loaderData is the kickstart info, can be NULL meaning no info
 *
 * requirepkgs=1 means CD should have packages, otherwise we just find stage2
 *
 * side effect: found cdrom is mounted on 'location' (usually /mnt/source, but
 * could also be /mnt/stage2 if we're just looking for a stage2 image).  stage2
 * mounted on /mnt/runtime.
 */
char * setupCdrom(char * location, struct loaderData_s * loaderData,
                  int interactive, int requirepkgs) {
    int i, r, rc;
    int foundinvalid = 0;
    int stage2inram = 0;
    char *buf, *stage2loc, *discinfoloc;
    char *stage2img;
    struct device ** devices;
    char *cddev = NULL;

    devices = getDevices(DEVICE_CDROM);
    if (!devices) {
        logMessage(ERROR, "got to setupCdrom without a CD device");
        return NULL;
    }

    if (loaderData && FL_STAGE2(flags)) {
        stage2loc = strdup(location);
        r = asprintf(&discinfoloc, "%s/.discinfo", imageDir);
    } else {
        r = asprintf(&stage2loc, "%s/images/stage2.img", location);
        r = asprintf(&discinfoloc, "%s/.discinfo", location);
    }

    /* JKFIXME: ASSERT -- we have a cdrom device when we get here */
    do {
        for (i = 0; devices[i]; i++) {
            char *tmp = NULL;

            if (!devices[i]->device)
                continue;

            if (strncmp("/dev/", devices[i]->device, 5)) {
                r = asprintf(&tmp, "/dev/%s", devices[i]->device);
                free(devices[i]->device);
                devices[i]->device = tmp;
            }

            logMessage(INFO,"trying to mount CD device %s on %s", devices[i]->device, location);

            if (!(rc=doPwMount(devices[i]->device, location, "iso9660", "ro"))) {
                cddev = devices[i]->device;
                if (!access(stage2loc, R_OK) &&
                    (!requirepkgs || !access(discinfoloc, R_OK))) {

                    /* if in rescue mode lets copy stage 2 into RAM so we can */
                    /* free up the CD drive and user can have it avaiable to  */
                    /* aid system recovery.                                   */
                    if (FL_RESCUE(flags) && !FL_TEXT(flags) &&
                        totalMemory() > 128000) {
                        rc = copyFile(stage2loc, "/tmp/stage2.img");
                        stage2img = "/tmp/stage2.img";
                        stage2inram = 1;
                    } else {
                        stage2img = strdup(stage2loc);
                        stage2inram = 0;
                    }
                    rc = mountStage2(stage2img);

                    if (rc) {
                        logMessage(INFO, "mounting stage2 failed");

                        umount(location);
                        if (rc == -1)
                            foundinvalid = 1;
                        continue;
                    }

                    /* do the media check */
                    if (requirepkgs)
                        queryCDMediaCheck(devices[i]->device, location);

                    /* if in rescue mode and we copied stage2 to RAM */
                    /* we can now unmount the CD                     */
                    if (FL_RESCUE(flags) && stage2inram) {
                        umount(location);
                    }

                    r = asprintf(&buf, "cdrom://%s:%s",
                                 devices[i]->device, location);

                    free(stage2loc);
                    free(discinfoloc);

                    if (r == -1)
                        return NULL;
                    else
                        return buf;

                }

                /* this wasnt the CD we were looking for, clean up and */
                /* try the next CD drive                               */
                umount(location);
            }
        }

        if (interactive) {
            char * buf;
            int i;
            if (foundinvalid)
                i = asprintf(&buf, _("No %s disc was found which matches your "
                                     "boot media.  Please insert the %s disc "
                                     "and press %s to retry."),
                        getProductName(), getProductName(), _("OK"));
            else
                i = asprintf(&buf, _("The %s disc was not found in any of your "
                                     "CDROM drives. Please insert the %s disc "
                                     "and press %s to retry."),
                        getProductName(), getProductName(), _("OK"));

            ejectCdrom(cddev);
            rc = newtWinChoice(_("Disc Not Found"),
                               _("OK"), _("Back"), buf, _("OK"));
            free(buf);
            if (rc == 2)
                goto err;
        } else {
            /* we can't ask them about it, so just return not found */
            goto err;
        }
    } while (1);

err:
    free(stage2loc);
    free(discinfoloc);
    return NULL;
}

/* try to find a install CD non-interactively */
char * findAnacondaCD(char * location, 
                    int requirepkgs) {
    return setupCdrom(location, NULL, 0, requirepkgs);
}

/* look for a CD and mount it.  if we have problems, ask */
char * mountCdromImage(struct installMethod * method,
                       char * location, struct loaderData_s * loaderData) {

    return setupCdrom(location, loaderData, 1, !FL_RESCUE(flags));
}

void setKickstartCD(struct loaderData_s * loaderData, int argc, char ** argv) {

    logMessage(INFO, "kickstartFromCD");
#if !defined(__s390__) && !defined(__s390x__)
    loaderData->method = METHOD_CDROM;
#endif
}

int kickstartFromCD(char *kssrc) {
    int rc, i;
    char *p, *kspath;
    struct device ** devices;

    logMessage(INFO, "getting kickstart file from first CDROM");

    devices = getDevices(DEVICE_CDROM);
    if (!devices) {
        logMessage(ERROR, "No CDROM devices found!");
        return 1;
    }

    /* format is cdrom:[/path/to/ks.cfg] */
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

    startNewt();
    newtWinMessage(_("Error"), _("OK"),
                   _("Cannot find kickstart file on CDROM."));
    return 1;
}

/* vim:set shiftwidth=4 softtabstop=4: */
