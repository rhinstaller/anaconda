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

#include "../isys/iface.h"
#include "../isys/log.h"

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

    if (FL_KICKSTART_SEND_SERIAL(flags) && !access("/sbin/dmidecode", X_OK)) {
        FILE *f;
        char sn[1024];
        size_t sn_len;

        if ((f = popen("/sbin/dmidecode -s system-serial-number", "r")) == NULL) {
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

static int loadSingleUrlImage(struct loaderData_s *loaderData, struct iurlinfo *ui,
                              char *dest, char *mntpoint, char *device, int silentErrors) {
    char **ehdrs = NULL;
    int status;

    if (!strncmp(ui->url, "http", 4))
        ehdrs = headers();

    status = urlinstTransfer(loaderData, ui, ehdrs, dest);
    if (status) {
        if (!silentErrors) {
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve %s."), ui->url);
        }

        return 2;
    }

    if (dest != NULL) {
        if (mountLoopback(dest, mntpoint, device)) {
            logMessage(ERROR, "Error mounting %s on %s: %m", device, mntpoint);
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

static int loadUrlImages(struct loaderData_s *loaderData, struct iurlinfo *ui) {
    char *oldUrl, *path, *dest, *slash;
    int rc;

    oldUrl = strdup(ui->url);
    free(ui->url);

    /* Figure out the path where updates.img and product.img files are
     * kept.  Since ui->url points to a stage2 image file, we just need
     * to trim off the file name and look in the same directory.
     */
    if ((slash = strrchr(oldUrl, '/')) == NULL)
        return 0;

    if ((path = strndup(oldUrl, slash-oldUrl)) == NULL)
        path = oldUrl;

    /* grab the updates.img before install.img so that we minimize our
     * ramdisk usage */
    checked_asprintf(&ui->url, "%s/%s", path, "updates.img");

    if (!loadSingleUrlImage(loaderData, ui, "/tmp/updates-disk.img", "/tmp/update-disk",
                            "/dev/loop7", 1)) {
        copyDirectory("/tmp/update-disk", "/tmp/updates", copyWarnFn,
                      copyErrorFn);
        umountLoopback("/tmp/update-disk", "/dev/loop7");
        unlink("/tmp/updates-disk.img");
        unlink("/tmp/update-disk");
    } else if (!access("/tmp/updates-disk.img", R_OK)) {
        unpackCpioBall("/tmp/updates-disk.img", "/tmp/updates");
        unlink("/tmp/updates-disk.img");
    }

    free(ui->url);

    /* grab the product.img before install.img so that we minimize our
     * ramdisk usage */
    checked_asprintf(&ui->url, "%s/%s", path, "product.img");

    if (!loadSingleUrlImage(loaderData, ui, "/tmp/product-disk.img", "/tmp/product-disk",
                            "/dev/loop7", 1)) {
        copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                      copyErrorFn);
        umountLoopback("/tmp/product-disk", "/dev/loop7");
        unlink("/tmp/product-disk.img");
        unlink("/tmp/product-disk");
    }

    free(ui->url);
    ui->url = strdup(oldUrl);

    checked_asprintf(&dest, "/tmp/install.img");

    rc = loadSingleUrlImage(loaderData, ui, dest, "/mnt/runtime", "/dev/loop0", 0);
    free(dest);
    free(oldUrl);

    if (rc) {
        if (rc != 2) 
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve the install image."));
        return 1;
    }

    return 0;
}

char *mountUrlImage(struct installMethod *method, char *location,
                    struct loaderData_s *loaderData) {
    urlInstallData *stage2Data = (urlInstallData *) loaderData->stage2Data;
    struct iurlinfo ui;

    enum { URL_STAGE_MAIN, URL_STAGE_FETCH,
           URL_STAGE_DONE } stage = URL_STAGE_MAIN;

    memset(&ui, 0, sizeof(ui));

    while (stage != URL_STAGE_DONE) {
        switch(stage) {
            case URL_STAGE_MAIN: {
                /* If the stage2= parameter was given (or inferred from repo=)
                 * then use that configuration info to fetch the image.  This
                 * could also have come from kickstart.  Else, we need to show
                 * the UI.
                 */
                if (loaderData->method == METHOD_URL && stage2Data) {
                    ui.url = strdup(stage2Data->url);
                    logMessage(INFO, "URL_STAGE_MAIN: url is %s", ui.url);

                    if (!ui.url) {
                        logMessage(ERROR, "missing URL specification");
                        loaderData->method = -1;
                        free(loaderData->stage2Data);
                        loaderData->stage2Data = NULL;

                        if (loaderData->inferredStage2)
                            loaderData->invalidRepoParam = 1;

                        break;
                    }

                    /* ks info was adequate, lets skip to fetching image */
                    stage = URL_STAGE_FETCH;
                    break;
                } else {
                    char *substr;

                    if (urlMainSetupPanel(loaderData, &ui)) {
                        loaderData->stage2Data = NULL;
                        return NULL;
                    }

                    /* If the user-provided URL points at a repo instead of
                     * a stage2 image, fix it up now.
                     */
                    substr = strstr(ui.url, ".img");
                    if (!substr || (substr && *(substr+4) != '\0')) {
                        loaderData->instRepo = strdup(ui.url);

                        checked_asprintf(&ui.url, "%s/images/install.img",
                                         ui.url);
                    }

                    loaderData->invalidRepoParam = 1;
                }

                stage = URL_STAGE_FETCH;
                break;
            }

            case URL_STAGE_FETCH: {
                if (loadUrlImages(loaderData, &ui)) {
                    stage = URL_STAGE_MAIN;

                    if (loaderData->method >= 0)
                        loaderData->method = -1;

                    if (loaderData->inferredStage2)
                        loaderData->invalidRepoParam = 1;
                } else {
                    stage = URL_STAGE_DONE;
                }

                break;
            }

            case URL_STAGE_DONE:
                break;
        }
    }

    return ui.url;
}

int getFileFromUrl(char * url, char * dest, 
                   struct loaderData_s * loaderData) {
    struct iurlinfo ui;
    char **ehdrs = NULL;
    int rc;
    iface_t iface;

    iface_init_iface_t(&iface);

    if (kickstartNetworkUp(loaderData, &iface)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    memset(&ui, 0, sizeof(ui));
    ui.url = url;

    logMessage(INFO, "file location: %s", url);

    if (!strncmp(url, "http", 4)) {
        ehdrs = headers();
    }

    rc = urlinstTransfer(loaderData, &ui, ehdrs, dest);
    if (rc) {
        logMessage(ERROR, "failed to retrieve %s", ui.url);
        return 1;
    }

    return 0;
}

/* pull kickstart configuration file via http */
int kickstartFromUrl(char * url, struct loaderData_s * loaderData) {
    return getFileFromUrl(url, "/tmp/ks.cfg", loaderData);
}

void setKickstartUrl(struct loaderData_s * loaderData, int argc,
		    char ** argv) {
    char *substr = NULL;
    gchar *url = NULL, *proxy = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksUrlOptions[] = {
        { "url", 0, 0, G_OPTION_ARG_STRING, &url, NULL, NULL },
        { "proxy", 0, 0, G_OPTION_ARG_STRING, &proxy, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromUrl");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksUrlOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to URL kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (!url) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Must supply a --url argument to Url kickstart method."));
        return;
    }

    /* determine install type */
    if (strncmp(url, "http", 4) && strncmp(url, "ftp://", 6)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        return;
    }

    substr = strstr(url, ".img");
    if (!substr || (substr && *(substr+4) != '\0')) {
        loaderData->instRepo = strdup(url);
    } else {
        if ((loaderData->stage2Data = calloc(sizeof(urlInstallData *), 1)) == NULL)
            return;

        ((urlInstallData *)loaderData->stage2Data)->url = url;
        loaderData->method = METHOD_URL;
    }

    if (proxy) {
        splitProxyParam(proxy, &loaderData->proxyUser,
			       &loaderData->proxyPassword,
			       &loaderData->proxy);
    }
    logMessage(INFO, "results of url ks, url %s", url);
}

/* vim:set shiftwidth=4 softtabstop=4: */
