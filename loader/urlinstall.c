/*
 * urlinstall.c - code to set up url (ftp/http) installs
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

#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>
#include <errno.h>
#include <glib.h>

#include "../pyanaconda/isys/iface.h"
#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/log.h"

#include "copy.h"
#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "method.h"
#include "net.h"
#include "method.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "urls.h"
#include "windows.h"
#include "unpack.h"

/* boot flags */
extern uint64_t flags;

char **extraHeaders = NULL;

static char **headers() {
    int len = 2;

    /* The list of HTTP headers is unlikely to change, unless a new ethernet
     * device suddenly shows up since last time we downloaded a file.  So,
     * cache the result here to save some time.
     */
    if (extraHeaders != NULL)
        return extraHeaders;

    if ((extraHeaders = realloc(extraHeaders, 2*sizeof(char *))) == NULL) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }
    
    checked_asprintf(&extraHeaders[0], "X-Anaconda-Architecture: %s", getProductArch());
    checked_asprintf(&extraHeaders[1], "X-Anaconda-System-Release: %s", getProductName());

    if (FL_KICKSTART_SEND_MAC(flags)) {
        /* find all ethernet devices and make a header entry for each one */
        int i;
        char *dev, *mac;
        struct device **devices;

        devices = getDevices(DEVICE_NETWORK);
        for (i = 0; devices && devices[i]; i++) {
            dev = devices[i]->device;
            mac = iface_mac2str(dev);

            if (mac) {
                extraHeaders = realloc(extraHeaders, (len+1)*sizeof(char *));
                checked_asprintf(&extraHeaders[len], "X-RHN-Provisioning-MAC-%d: %s %s",
                                 i, dev, mac);

                len++;
                free(mac);
            }
        }
    }

    if (FL_KICKSTART_SEND_SERIAL(flags) && !access("/usr/sbin/dmidecode", X_OK)) {
        FILE *f;
        char sn[1024];
        size_t sn_len;

        if ((f = popen("/usr/sbin/dmidecode -s system-serial-number", "r")) == NULL) {
            logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

        sn_len = fread(sn, sizeof(char), 1023, f);
        if (ferror(f)) {
            logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

        sn[sn_len] = '\0';
        pclose(f);

        extraHeaders = realloc(extraHeaders, (len+1)*sizeof(char *));

        checked_asprintf(&extraHeaders[len], "X-System-Serial-Number: %s", sn);

        len++;
    }

    extraHeaders = realloc(extraHeaders, (len+1)*sizeof(char *));
    extraHeaders[len] = NULL;
    return extraHeaders;
}

static int loadSingleUrlImage(struct loaderData_s *loaderData, const char *src,
                              char *dest, char *mntpoint, int silentErrors) {
    char **ehdrs = NULL;
    int status;

    if (!strncmp(src, "http", 4))
        ehdrs = headers();

    status = urlinstTransfer(loaderData, src, ehdrs, dest);
    if (status) {
        if (!silentErrors) {
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve %s."), src);
        }

        return 2;
    }

    if (dest != NULL) {
        if (doPwMount(dest, mntpoint, "auto", "ro", NULL)) {
            logMessage(ERROR, "Error mounting %s: %m", dest);
            return 1;
        }
    }

    return 0;
}

static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

int loadUrlImages(struct loaderData_s *loaderData) {
    char *url;

    logMessage(DEBUGLVL, "looking for extras for HTTP/FTP install");

    if (!loaderData->instRepo)
        return 0;

    checked_asprintf(&url, "%s/images/%s", loaderData->instRepo, "updates.img");

    if (!loadSingleUrlImage(loaderData, url, "/tmp/updates-disk.img", "/tmp/update-disk", 1)) {
        copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                      copyErrorFn);
        umount("/tmp/update-disk");
        unlink("/tmp/updates-disk.img");
        unlink("/tmp/update-disk");
    } else if (!access("/tmp/updates-disk.img", R_OK)) {
        unpack_archive_file("/tmp/updates-disk.img", "/tmp/updates");
        unlink("/tmp/updates-disk.img");
    }

    free(url);

    checked_asprintf(&url, "%s/images/%s", loaderData->instRepo, "product.img");

    if (!loadSingleUrlImage(loaderData, url, "/tmp/product-disk.img", "/tmp/product-disk", 1)) {
        copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                      copyErrorFn);
        umount("/tmp/product-disk");
        unlink("/tmp/product-disk.img");
        unlink("/tmp/product-disk");
    }

    free(url);
    return 0;
}

int promptForUrl(struct loaderData_s *loaderData) {
    char *url;

    do {
        if (urlMainSetupPanel(loaderData) == LOADER_BACK) {
            loaderData->instRepo = NULL;
            return LOADER_BACK;
        }

        checked_asprintf(&url, "%s/.treeinfo", loaderData->instRepo);

        if (getFileFromUrl(url, "/tmp/.treeinfo", loaderData)) {
            newtWinMessage(_("Error"), _("OK"),
                           _("The URL provided does not contain installation media."));
            free(url);
            continue;
        }

        free(url);
        break;
    } while (1);

    return LOADER_OK;
}

int getFileFromUrl(char * url, char * dest, 
                   struct loaderData_s * loaderData) {
    char **ehdrs = NULL;
    int rc;
    iface_t iface;

    iface_init_iface_t(&iface);

    if (kickstartNetworkUp(loaderData, &iface)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    logMessage(INFO, "file location: %s", url);

    if (!strncmp(url, "http", 4)) {
        ehdrs = headers();
    }

    rc = urlinstTransfer(loaderData, url, ehdrs, dest);
    if (rc) {
        logMessage(ERROR, "failed to retrieve %s", url);
        return 1;
    }

    return 0;
}

/* pull kickstart configuration file via http */
int kickstartFromUrl(char * url, struct loaderData_s * loaderData) {
    return getFileFromUrl(url, "/tmp/ks.cfg", loaderData);
}

/* vim:set shiftwidth=4 softtabstop=4: */
