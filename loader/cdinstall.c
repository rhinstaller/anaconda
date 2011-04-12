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
/* FIXME Remove hack when: https://bugzilla.redhat.com/show_bug.cgi?id=478663
   is resolved */
/* Hack both __BIG_ENDIAN and __LITTLE_ENDIAN get defined by glibc, the
   kernel headers we need do not like this! */
#if __BYTE_ORDER == __LITTLE_ENDIAN
#undef __BIG_ENDIAN 
#else
#undef __LITTLE_ENDIAN
#endif
#include <asm/types.h>
#include <limits.h>
#include <linux/cdrom.h>

#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "modules.h"
#include "method.h"
#include "cdinstall.h"
#include "mediacheck.h"
#include "windows.h"

#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/log.h"
#include "../pyanaconda/isys/mem.h"

/* boot flags */
extern uint64_t flags;

/* ejects the CD device the device node points at */
static void ejectCdrom(char *device) {
    int ejectfd;

    if (!device) return;

    if (FL_NOEJECT(flags)) {
        logMessage(INFO, "noeject in effect, not ejecting cdrom");
        return;
    }

    logMessage(INFO, "ejecting %s...",device);
    if ((ejectfd = open(device, O_RDONLY | O_NONBLOCK, 0)) >= 0) {
        ioctl(ejectfd, CDROM_LOCKDOOR, 0);
        if (ioctl(ejectfd, CDROMEJECT, 0))
            logMessage(ERROR, "eject failed on device %s: %m", device);
        close(ejectfd);
    } else {
        logMessage(ERROR, "could not open device %s: %m", device);
    }
}

static char *cdrom_drive_status(int rc) {
    struct {
        int code;
        char *str;
    } status_codes[] =
        {
            { CDS_NO_INFO, "CDS_NO_INFO" },
            { CDS_NO_DISC, "CDS_NO_DISC" },
            { CDS_TRAY_OPEN, "CDS_TRAY_OPEN" },
            { CDS_DRIVE_NOT_READY, "CDS_DRIVE_NOT_READY" },
            { CDS_DISC_OK, "CDS_DISC_OK" },
            { CDS_AUDIO, "CDS_AUDIO" },
            { CDS_DATA_1, "CDS_DATA_1" },
            { CDS_DATA_2, "CDS_DATA_2" },
            { CDS_XA_2_1, "CDS_XA_2_1" },
            { CDS_XA_2_2, "CDS_XA_2_2" },
            { CDS_MIXED, "CDS_MIXED" },
            { INT_MAX, NULL },
        };
    int i;

    if (rc < 0)
        return strerror(-rc);

    for (i = 0; status_codes[i].code != INT_MAX; i++) {
        if (status_codes[i].code == rc)
            return status_codes[i].str;
    }
    return NULL;
}

static int waitForCdromTrayClose(int fd) {
    int rc;
    int prev = INT_MAX;

    do {
        char *status = NULL;
        rc = ioctl(fd, CDROM_DRIVE_STATUS, CDSL_CURRENT);
        if (rc < 0)
            rc = -errno;

        /* only bother to print the status if it changes */
        if (prev == INT_MAX || prev != rc) {
            status = cdrom_drive_status(rc);
            if (status != NULL) {
                logMessage(INFO, "drive status is %s", status);
            } else {
                logMessage(INFO, "drive status is unknown status code %d", rc);
            }
        }
        prev = rc;
        if (rc == CDS_DRIVE_NOT_READY)
            usleep(100000);
    } while (rc == CDS_DRIVE_NOT_READY);
    return rc;
}

static void closeCdromTray(char *device) {
    int fd;

    if (!device || !*device)
        return;

    logMessage(INFO, "closing CD tray on %s .", device);
    if ((fd = open(device, O_RDONLY | O_NONBLOCK, 0)) >= 0) {
        if (ioctl(fd, CDROMCLOSETRAY, 0)) {
            logMessage(ERROR, "closetray failed on device %s: %m", device);
        } else {
            waitForCdromTrayClose(fd);
            ioctl(fd, CDROM_LOCKDOOR, 1);
        }
        close(fd);
    } else {
        logMessage(ERROR, "could not open device %s: %m", device);
    }
}

/* Given cd device cddriver, this function will attempt to check its internal
 * checksum.
 */
static void mediaCheckCdrom(char *cddriver) {
    char *descr, *tstamp;

    closeCdromTray(cddriver);
    readStampFileFromIso(cddriver, &tstamp, &descr);
    doMediaCheck(cddriver, descr);

    if (descr)
        free(descr);

    if (tstamp)
        free(tstamp);
}

/* output an error message when CD in drive is not the correct one */
/* Used by mountCdromStage2()                                      */
static void wrongCDMessage(void) {
    newtWinMessage(_("Error"), _("OK"),
                   _("The %s disc was not found "
                     "in any of your drives. Please insert "
                     "the %s disc and press %s to retry."),
                   getProductName(), getProductName(), _("OK"));
}

/* ask about doing media check */
void queryCDMediaCheck(char *instRepo) {
    int rc;
    char *tmp, *device;

    /* dont bother to test in automated installs */
    if (FL_KICKSTART(flags) && !FL_MEDIACHECK(flags))
        return;

    /* Skip over the leading "cdrom://". */
    tmp = instRepo+8;
    checked_asprintf(&device, "%.*s", (int) (strchr(tmp, ':')-tmp), tmp);

    /* see if we should check image(s) */
    /* in rescue mode only test if they explicitly asked to */
    if (!FL_RESCUE(flags) || FL_MEDIACHECK(flags)) {
        startNewt();
        rc = newtWinChoice(_("Disc Found"), _("OK"), _("Skip"),
             _("To begin testing the media before installation press %s.\n\n"
               "Choose %s to skip the media test and start the installation."),
             _("OK"), _("Skip"));

        if (rc != 2) {
            /* We already mounted the CD earlier to verify there's installation
             * media.  Now we need to unmount it to perform the check, then
             * remount to pretend nothing ever happened.
             */
            umount("/mnt/install/source");
            mediaCheckCdrom(device);

            do {
                if (doPwMount(device, "/mnt/install/source", "iso9660", "ro", NULL)) {
                    ejectCdrom(device);
                    wrongCDMessage();
                    continue;
                }

                if (access("/mnt/install/source/.discinfo", R_OK)) {
                    umount("/mnt/install/source");
                    ejectCdrom(device);
                    wrongCDMessage();
                    continue;
                }

                break;
            } while (1);
        }
    }

    free(device);
}

int findInstallCD(struct loaderData_s *loaderData) {
    int i, rc;
    struct device **devices;

    devices = getDevices(DEVICE_CDROM);
    if (!devices) {
        logMessage(ERROR, "got to findInstallCD without a CD device");
        return LOADER_ERROR;
    }

    for (i = 0; devices[i]; i++) {
        char *tmp = NULL;
        int fd;

        if (!devices[i]->device)
            continue;

        if (strncmp("/dev/", devices[i]->device, 5)) {
            checked_asprintf(&tmp, "/dev/%s", devices[i]->device);

            free(devices[i]->device);
            devices[i]->device = tmp;
        }

        logMessage(INFO, "trying to mount CD device %s on /mnt/install/source",
                   devices[i]->device);

        if (!FL_CMDLINE(flags))
            winStatus(60, 3, _("Scanning"), _("Looking for installation media on CD device %s\n"), devices[i]->device);
        else
            printf(_("Looking for installation media on CD device %s"), devices[i]->device);

        fd = open(devices[i]->device, O_RDONLY | O_NONBLOCK);
        if (fd < 0) {
            logMessage(ERROR, "Couldn't open %s: %m", devices[i]->device);
            if (!FL_CMDLINE(flags))
                newtPopWindow();
            continue;
        }

        rc = waitForCdromTrayClose(fd);
        close(fd);
        switch (rc) {
            case CDS_NO_INFO:
                logMessage(ERROR, "Drive tray reports CDS_NO_INFO");
                break;
            case CDS_NO_DISC:
                if (!FL_CMDLINE(flags))
                        newtPopWindow();
                continue;
            case CDS_TRAY_OPEN:
                logMessage(ERROR, "Drive tray reports open when it should be closed");
                break;
            default:
                break;
        }

        if (!FL_CMDLINE(flags))
            newtPopWindow();

        if ((rc = doPwMount(devices[i]->device, "/mnt/install/source", "iso9660", "ro", NULL)) == 0) {
            if (!access("/mnt/install/source/.treeinfo", R_OK) && !access("/mnt/install/source/.discinfo", R_OK)) {
                 loaderData->method = METHOD_CDROM;
                 checked_asprintf(&loaderData->instRepo, "cdrom://%s:/mnt/install/source", devices[i]->device);
                 return LOADER_OK;
            } else {
                /* This wasn't the CD we were looking for.  Clean up and
                 * try the next drive.
                 */
                umount("/mnt/install/source");
            }
        }
    }

    return LOADER_ERROR;
}

int promptForCdrom(struct loaderData_s *loaderData) {
    int rc;

    do {
        rc = findInstallCD(loaderData);

        if (loaderData->instRepo && rc == LOADER_OK) {
            queryCDMediaCheck(loaderData->instRepo);
            return rc;
        } else {
            char * buf;

            checked_asprintf(&buf, _("The %s disc was not found in any of your "
                                     "CDROM drives. Please insert the %s disc "
                                     "and press %s to retry."),
                             getProductName(), getProductName(), _("OK"));

            rc = newtWinChoice(_("Disc Not Found"),
                               _("OK"), _("Back"), buf, _("OK"));
            free(buf);
            if (rc == 2)
                return LOADER_BACK;
        }
    } while (!loaderData->instRepo);

    return LOADER_OK;
}

int loadCdromImages(struct loaderData_s *loaderData) {
    char *device = NULL;
    char *tmp;

    logMessage(DEBUGLVL, "looking for extras for CD/DVD install");

    if (!loaderData->instRepo)
        return 0;

    /* Skip over the leading "cdrom://". */
    tmp = loaderData->instRepo+8;
    checked_asprintf(&device, "%.*s", (int) (strchr(tmp, ':')-tmp), tmp);

    if (doPwMount(device, "/mnt/install/source", "auto", "ro", NULL))
        return 0;

    logMessage(INFO, "Looking for updates in /mnt/install/source/images/updates.img");
    copyUpdatesImg("/mnt/install/source/images/updates.img");

    logMessage(INFO, "Looking for product in /mnt/install/source/images/product.img");
    copyProductImg("/mnt/install/source/images/product.img");

    umount("/mnt/install/source");
    return 1;
}

int kickstartFromCD(char *kssrc) {
    int rc, i;
    char *p, *kspath;
    struct device ** devices;

    logMessage(INFO, "getting kickstart file from first CDROM");

    devices = getDevices(DEVICE_CDROM);
    /* usb can take some time to settle, even with the various hacks we
     * have in place.  some systems use portable USB CD-ROM drives, try to
     * make sure there really isn't one before bailing */
    for (i = 0; !devices && i < 10; ++i) {
        logMessage(INFO, "sleeping to wait for a USB CD-ROM");
        sleep(2);
        devices = getDevices(DEVICE_CDROM);
    }
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

/* vim:set shiftwidth=4 softtabstop=4 et */
