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
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <unistd.h>
#include <errno.h>

#include "../isys/iface.h"

#include "copy.h"
#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "method.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "urls.h"
#include "windows.h"

/* boot flags */
extern uint64_t flags;

static int loadSingleUrlImage(struct iurlinfo * ui, char *path,
                              char * dest, char * mntpoint, char * device,
                              int silentErrors) {
    int fd;
    int rc = 0;
    char *ehdrs = NULL;

    if (ui->protocol == URL_METHOD_HTTP) {
        char *arch = getProductArch();
        char *name = getProductName();

        if (asprintf(&ehdrs, "User-Agent: anaconda/%s\r\n"
                             "X-Anaconda-Architecture: %s\r\n"
                             "X-Anaconda-System-Release: %s\r\n",
                     VERSION, arch, name) == -1) {
            logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                       strerror(errno));
            abort();
        }
    }

    fd = urlinstStartTransfer(ui, path, ehdrs);

    if (fd == -2) {
        if (ehdrs) free (ehdrs);
        return 2;
    }
    else if (fd < 0) {
        if (!silentErrors) {
            newtWinMessage(_("Error"), _("OK"),
                           _("Unable to retrieve %s://%s%s."),
                           (ui->protocol == URL_METHOD_FTP ? "ftp" : "http"),
                           ui->address, path);
        }

        if (ehdrs) free (ehdrs);
        return 2;
    }

    if (dest != NULL) {
        rc = copyFileAndLoopbackMount(fd, dest, device, mntpoint);
    }

    urlinstFinishTransfer(ui, fd);
    return rc;
}

static void copyWarnFn (char *msg) {
   logMessage(WARNING, msg);
}

static void copyErrorFn (char *msg) {
   newtWinMessage(_("Error"), _("OK"), _(msg));
}

static int loadUrlImages(struct iurlinfo * ui) {
    char *buf, *path, *dest, *slash;
    int rc;

    /* Figure out the path where updates.img and product.img files are
     * kept.  Since ui->prefix points to a stage2 image file, we just need
     * to trim off the file name and look in the same directory.
     */
    if ((slash = strrchr(ui->prefix, '/')) == NULL)
        return 0;

    if ((path = strndup(ui->prefix, slash - ui->prefix)) == NULL)
        path = ui->prefix;

    /* grab the updates.img before stage2.img so that we minimize our
     * ramdisk usage */
    if (asprintf(&buf, "%s/%s", path, "updates.img") == -1) {
        logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                   strerror(errno));
        abort();
    }

    if (!loadSingleUrlImage(ui, buf,
                            "/tmp/updates-disk.img", "/tmp/update-disk",
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

    free(buf);

    /* grab the product.img before stage2.img so that we minimize our
     * ramdisk usage */
    if (asprintf(&buf, "%s/%s", path, "product.img") == -1) {
        logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                   strerror(errno));
        abort();
    }

    if (!loadSingleUrlImage(ui, buf,
                            "/tmp/product-disk.img", "/tmp/product-disk",
                            "/dev/loop7", 1)) {
        copyDirectory("/tmp/product-disk", "/tmp/product", copyWarnFn,
                      copyErrorFn);
        umountLoopback("/tmp/product-disk", "/dev/loop7");
        unlink("/tmp/product-disk.img");
        unlink("/tmp/product-disk");
    }

    free(buf);

    if (asprintf(&dest, "/tmp/stage2.img") == -1) {
        logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                   strerror(errno));
        abort();
    }

    rc = loadSingleUrlImage(ui, ui->prefix, dest, "/mnt/runtime", "/dev/loop0", 0);
    free(dest);

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
    struct iurlinfo ui;
    char *url = NULL;

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
                if (loaderData->method == METHOD_URL && loaderData->stage2Data) {
                    url = ((struct urlInstallData *) loaderData->stage2Data)->url;
                    logMessage(INFO, "URL_STAGE_MAIN: url is %s", url);

                    if (!url) {
                        logMessage(ERROR, "missing URL specification");
                        loaderData->method = -1;
                        free(loaderData->stage2Data);
                        loaderData->stage2Data = NULL;
                        break;
                    }

                    /* explode url into ui struct */
                    convertURLToUI(url, &ui);

                    /* ks info was adequate, lets skip to fetching image */
                    stage = URL_STAGE_FETCH;
                    break;
                } else {
                    char *substr;

                    if (urlMainSetupPanel(&ui))
                        return NULL;

                    /* If the user-provided URL points at a repo instead of
                     * a stage2 image, fix it up now.
                     */
                    substr = strstr(ui.prefix, ".img");
                    if (!substr || (substr && *(substr+4) != '\0')) {
                        char *stage2img;

                        /* Pick the right stage2 image depending on the
                         * amount of memory.
                         */
                        if (totalMemory() < GUI_STAGE2_RAM) {
                            stage2img = "minstg2.img";
                            logMessage(WARNING, "URLINSTALL falling back to non-GUI stage2 "
                                                "due to insufficient RAM");
                        } else {
                            stage2img = "stage2.img";
                        }

                        if (asprintf(&ui.prefix, "%s/images/%s", ui.prefix,
                                     stage2img) == -1) {
                            logMessage(CRITICAL, "%s: %d: %s", __func__,
                                       __LINE__, strerror(errno));
                            abort();
                        }
                    }
                }

                stage = URL_STAGE_FETCH;
                break;
            }

            case URL_STAGE_FETCH: {
                if (FL_TESTING(flags)) {
                    stage = URL_STAGE_DONE;
                    break;
                }

                if (loadUrlImages(&ui)) {
                    stage = URL_STAGE_MAIN;

                    if (loaderData->method >= 0)
                        loaderData->method = -1;
                } else {
                    stage = URL_STAGE_DONE;
                }

                break;
            }

            case URL_STAGE_DONE:
                break;
        }
    }

    url = convertUIToURL(&ui);
    return url;
}

int getFileFromUrl(char * url, char * dest, 
                   struct loaderData_s * loaderData) {
    int retval = 0;
    struct iurlinfo ui;
    enum urlprotocol_t proto = 
        !strncmp(url, "ftp://", 6) ? URL_METHOD_FTP : URL_METHOD_HTTP;
    char * host = NULL, * file = NULL, * chptr = NULL, *login = NULL, *password = NULL;
    int fd, rc;
    struct networkDeviceConfig netCfg;
    char *ehdrs = NULL, *ip = NULL;

    if (kickstartNetworkUp(loaderData, &netCfg)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    memset(&ui, 0, sizeof(ui));
    ui.protocol = proto;

    if ((ip = iface_ip2str(loaderData->netDev)) == NULL) {
        logMessage(ERROR, "getFileFromUrl: no client IP information");
        return 1;
    }

    getHostPathandLogin((proto == URL_METHOD_FTP ? url + 6 : url + 7),
                   &host, &file, &login, &password, ip);

    logMessage(INFO, "file location: %s://%s%s", 
               (proto == URL_METHOD_FTP ? "ftp" : "http"), host, file);

    chptr = strchr(host, '/');
    if (chptr == NULL) {
        ui.address = strdup(host);
        ui.prefix = strdup("/");
    } else {
        *chptr = '\0';
        ui.address = strdup(host);
        host = chptr;
        *host = '/';
        ui.prefix = strdup(host);
    }

    if (password[0] != '\0')
        ui.password = strdup (password);
    if (login[0] != '\0')
        ui.login = strdup (login);

    if (proto == URL_METHOD_HTTP) {
        char *arch = getProductArch();
        char *name = getProductName();

        if (asprintf(&ehdrs, "User-Agent: anaconda/%s\r\n"
                             "X-Anaconda-Architecture: %s\r\n"
                             "X-Anaconda-System-Release: %s\r\n",
                     VERSION, arch, name) == -1) {
            logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                       strerror(errno));
            abort();
        }
    }

    if (proto == URL_METHOD_HTTP && FL_KICKSTART_SEND_MAC(flags)) {
        /* find all ethernet devices and make a header entry for each one */
        int i;
        char *dev, *mac, *tmpstr;
        struct device **devices;

        devices = getDevices(DEVICE_NETWORK);
        for (i = 0; devices && devices[i]; i++) {
            dev = devices[i]->device;
            mac = iface_mac2str(dev);

            if (mac) {
                if (asprintf(&tmpstr, "X-RHN-Provisioning-MAC-%d: %s %s\r\n",
                             i, dev, mac) == -1) {
                    logMessage(CRITICAL, "%s: %d: %s", __func__, __LINE__,
                               strerror(errno));
                    abort();
                }

                if (!ehdrs) {
                    ehdrs = strdup(tmpstr);
                } else {
                    ehdrs = (char *) realloc(ehdrs, strlen(ehdrs)+strlen(tmpstr)+1);
                    strcat(ehdrs, tmpstr);
                }

                free(mac);
                free(tmpstr);
            }
        }
    }

    fd = urlinstStartTransfer(&ui, file, ehdrs);
    if (fd < 0) {
        logMessage(ERROR, "failed to retrieve http://%s/%s%s", ui.address, ui.prefix, file);
        retval = 1;
        goto err;
    }

    rc = copyFileFd(fd, dest);
    if (rc) {
        unlink (dest);
        logMessage(ERROR, "failed to copy file to %s", dest);
        retval = 1;
        goto err;
    }

    urlinstFinishTransfer(&ui, fd);

err:
    if (file) free(file);
    if (ehdrs) free(ehdrs);
    if (host) free(host);
    if (login) free(login);
    if (password) free(password);

    return retval;
}

/* pull kickstart configuration file via http */
int kickstartFromUrl(char * url, struct loaderData_s * loaderData) {
    return getFileFromUrl(url, "/tmp/ks.cfg", loaderData);
}

void setKickstartUrl(struct loaderData_s * loaderData, int argc,
		    char ** argv) {

    char *url = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksUrlOptions[] = {
        { "url", '\0', POPT_ARG_STRING, &url, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    logMessage(INFO, "kickstartFromUrl");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksUrlOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to Url kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    if (!url) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Must supply a --url argument to Url kickstart method."));
        return;
    }

    /* determine install type */
    if (strstr(url, "http://") || strstr(url, "ftp://"))
	loaderData->method = METHOD_URL;
    else {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        return;
    }

    if ((loaderData->stage2Data = calloc(sizeof(struct urlInstallData *), 1)) == NULL)
        return;

    ((struct urlInstallData *)loaderData->stage2Data)->url = url;

    logMessage(INFO, "results of url ks, url %s", url);
}

/* vim:set shiftwidth=4 softtabstop=4: */
