/*
 * urlinstall.c - code to set up url (ftp/http) installs
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

#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "../isys/getmacaddr.h"

#include "kickstart.h"
#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "method.h"
#include "urlinstall.h"
#include "urls.h"

static int loadSingleUrlImage(struct iurlinfo * ui, char * file, int flags, 
                              char * dest, char * mntpoint, char * device,
                              int silentErrors) {
    int fd;
    int rc;
    char * newFile = NULL;

    fd = urlinstStartTransfer(ui, file, NULL, 1, flags);

    if (fd == -2) return 1;

    if (fd < 0) {
        /* file not found */

        newFile = alloca(strlen(device) + 20);
        sprintf(newFile, "disc1/%s", file);

        fd = urlinstStartTransfer(ui, newFile, NULL, 1, flags);

        if (fd == -2) return 1;
        if (fd < 0) {
            if (!silentErrors) 
                newtWinMessage(_("Error"), _("OK"),
                               _("Unable to retrieve %s://%s/%s/%s."),
                               (ui->protocol == URL_METHOD_FTP ? "ftp" : 
                                "http"),
                               ui->address, ui->prefix, file);
            return 1;
        }
    }

    rc = copyFileAndLoopbackMount(fd, dest, flags, device, mntpoint);

    urlinstFinishTransfer(ui, fd, flags);

    if (newFile) {
        newFile = malloc(strlen(ui->prefix ) + 20);
        sprintf(newFile, "%s/disc1", ui->prefix);
        free(ui->prefix);
        ui->prefix = newFile;
    }

    return rc;
}


static int loadUrlImages(struct iurlinfo * ui, int flags) {
    /*    setupRamdisk();*/

    /* grab the updates.img before netstg1.img so that we minimize our
     * ramdisk usage */
    if (!loadSingleUrlImage(ui, "RedHat/base/updates.img", flags,
                            "/tmp/ramfs/updates-disk.img", "/tmp/update-disk",
                            "loop7", 1)) {
        copyDirectory("/tmp/update-disk", "/tmp/updates");
        umountLoopback("/tmp/update-disk", "loop7");
        unlink("/tmp/ramfs/updates-disk.img");
        unlink("/tmp/update-disk");
    }

    /* grab the product.img before netstg1.img so that we minimize our
     * ramdisk usage */
    if (!loadSingleUrlImage(ui, "RedHat/base/product.img", flags,
                            "/tmp/ramfs/product-disk.img", "/tmp/product-disk",
                            "loop7", 1)) {
        copyDirectory("/tmp/product-disk", "/tmp/product");
        umountLoopback("/tmp/product-disk", "loop7");
        unlink("/tmp/ramfs/product-disk.img");
        unlink("/tmp/product-disk");
    }

    if (loadSingleUrlImage(ui, "RedHat/base/netstg2.img", flags,
                           "/tmp/ramfs/netstg2.img",
                           "/mnt/runtime", "loop0", 0)) {
        newtWinMessage(_("Error"), _("OK"),
                       _("Unable to retrieve the install image."));
        return 1;
    }

    /* now verify the stamp... */
    if (!verifyStamp("/mnt/runtime")) {
	char * buf;

	buf = sdupprintf(_("The %s installation tree in that directory does "
			   "not seem to match your boot media."), 
                         getProductName());

	newtWinMessage(_("Error"), _("OK"), buf);

	umountLoopback("/mnt/runtime", "loop0");
	return 1;
    }

    return 0;

}

static char * getLoginName(char * login, struct iurlinfo ui) {
    int i;

    i = 0;
    /* password w/o login isn't useful */
    if (ui.login && strlen(ui.login)) {
        i += strlen(ui.login) + 5;
        if (strlen(ui.password))
            i += 3*strlen(ui.password) + 5;
        
        if (ui.login || ui.password) {
            login = malloc(i);
            strcpy(login, ui.login);
            if (ui.password) {
                char * chptr;
                char code[4];
                
                strcat(login, ":");
                for (chptr = ui.password; *chptr; chptr++) {
                    sprintf(code, "%%%2x", *chptr);
                    strcat(login, code);
                }
                strcat(login, "@");
            }
        }
    }
    
    return login;
}

char * mountUrlImage(struct installMethod * method,
                     char * location, struct knownDevices * kd,
                     struct loaderData_s * loaderData,
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDeps, int flags) {
    int rc;
    char * url, *p;
    struct iurlinfo ui;
    char needsSecondary = ' ';
    int dir = 1;
    char * login;
    char * finalPrefix;

    enum { URL_STAGE_MAIN, URL_STAGE_SECOND, URL_STAGE_FETCH, 
           URL_STAGE_DONE } stage = URL_STAGE_MAIN;

    enum urlprotocol_t proto = 
        !strcmp(method->name, "FTP") ? URL_METHOD_FTP : URL_METHOD_HTTP;

    /* JKFIXME: we used to do another ram check here... keep it? */

    memset(&ui, 0, sizeof(ui));

    while (stage != URL_STAGE_DONE) {
        switch(stage) {
        case URL_STAGE_MAIN:
            if (loaderData->method && *loaderData->method &&
                (!strncmp(loaderData->method, "ftp", 3) ||
		 !strncmp(loaderData->method, "http", 3)) &&
                loaderData->methodData) {
		
                url = ((struct urlInstallData *)loaderData->methodData)->url;

                logMessage("URL_STAGE_MAIN - url is %s", url);

                if (!url) {
                    logMessage("missing url specification");
                    free(loaderData->method);
                    loaderData->method = NULL;
                    break;
                }
		
		/* explode url into ui struct */
		convertURLToUI(url, &ui);

		/* ks info was adequate, lets skip to fetching image */
		stage = URL_STAGE_FETCH;
		dir = 1;
		break;
	    } else if (urlMainSetupPanel(&ui, proto, &needsSecondary)) {
                return NULL;
            }

	    /* got required information from user, proceed */
	    stage = (needsSecondary != ' ') ? URL_STAGE_SECOND : 
		URL_STAGE_FETCH;
	    dir = 1;
            break;

        case URL_STAGE_SECOND:
            rc = urlSecondarySetupPanel(&ui, proto);
            if (rc) {
                stage = URL_STAGE_MAIN;
                dir = -1;
            } else {
                stage = URL_STAGE_FETCH;
                dir = 1;
            }
            break;

        case URL_STAGE_FETCH:
            if (FL_TESTING(flags)) {
                stage = URL_STAGE_DONE;
                dir = 1;
                break;
            }

            if (loadUrlImages(&ui, flags)) {
                stage = URL_STAGE_MAIN;
                dir = -1;
                if (loaderData->method) {
                    free(loaderData->method);
                    loaderData->method = NULL;
                }
            } else {
                stage = URL_STAGE_DONE;
                dir = 1;
            }
            break;

        case URL_STAGE_DONE:
            break;
        }
    }

    login = "";
    login = getLoginName(login, ui);

    if (!strcmp(ui.prefix, "/"))
        finalPrefix = "/.";
    else
        finalPrefix = ui.prefix;

    url = malloc(strlen(finalPrefix) + 25 + strlen(ui.address) +
                 strlen(login));

    /* sanitize url so we dont have problems like bug #101265 */
    /* basically avoid duplicate /'s                          */
    for (p=finalPrefix; *p == '/'; p++);

    finalPrefix = p;

    sprintf(url, "%s://%s%s/%s", 
	    ui.protocol == URL_METHOD_FTP ? "ftp" : "http",
	    login, ui.address, finalPrefix);

    return url;
}

int getFileFromUrl(char * url, char * dest, struct knownDevices * kd,
                   struct loaderData_s * loaderData, int flags) {
    struct iurlinfo ui;
    enum urlprotocol_t proto = 
        !strncmp(url, "ftp://", 6) ? URL_METHOD_FTP : URL_METHOD_HTTP;
    char * host = NULL, * file = NULL, * chptr = NULL;
    int fd, rc;
    struct networkDeviceConfig netCfg;
    char * ehdrs;

    if (kickstartNetworkUp(kd, loaderData, &netCfg, flags)) {
        logMessage("unable to bring up network");
        return 1;
    }

    memset(&ui, 0, sizeof(ui));
    ui.protocol = proto;

    getHostandPath((proto == URL_METHOD_FTP ? url + 6 : url + 7), 
                   &host, &file, inet_ntoa(netCfg.dev.ip));

    logMessage("ks location: %s://%s/%s", 
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

    ehdrs = NULL;
    if (proto == URL_METHOD_HTTP && FL_KICKSTART_SEND_MAC(flags)) {
	/* find all ethernet devices and make a header entry for each one */
	int i, hdrlen;
	char *dev, *mac, tmpstr[128];

	hdrlen = 0;
	for (i = 0; i < kd->numKnown; i++) {
	    if (kd->known[i].class != CLASS_NETWORK)
		continue;
	    
	    dev = kd->known[i].name;
	    mac = getMacAddr(dev);

	    if (mac) {
		snprintf(tmpstr, sizeof(tmpstr), "X-RHN-Provisioning-MAC-%d: %s %s\r\n", i, dev, mac);
		free(mac);

		if (!ehdrs) {
		    hdrlen = 128;
		    ehdrs = (char *) malloc(hdrlen);
		    *ehdrs = '\0';
		} else if ( strlen(tmpstr) + strlen(ehdrs) +2 > hdrlen) {
		    hdrlen += 128;
		    ehdrs = (char *) realloc(ehdrs, hdrlen);
		}

		strcat(ehdrs, tmpstr);
	    }
	}
    }

    fd = urlinstStartTransfer(&ui, file, ehdrs, 1, flags);
    if (fd < 0) {
        logMessage("failed to retrieve http://%s/%s/%s", ui.address, ui.prefix, file);
        return 1;
    }
           
    rc = copyFileFd(fd, dest);
    if (rc) {
        unlink (dest);
        logMessage("failed to copy file to %s", dest);
        return 1;
    }

    urlinstFinishTransfer(&ui, fd, flags);

    return 0;
}

/* pull kickstart configuration file via http */
int kickstartFromUrl(char * url, struct knownDevices * kd,
                     struct loaderData_s * loaderData, int flags) {
    return getFileFromUrl(url, "/tmp/ks.cfg", kd, loaderData, flags);
}

void setKickstartUrl(struct knownDevices * kd, 
                     struct loaderData_s * loaderData, int argc,
		    char ** argv, int * flagsPtr) {

    char *url;
    poptContext optCon;
    int rc;
    struct poptOption ksUrlOptions[] = {
        { "url", '\0', POPT_ARG_STRING, &url, 0 },
        { 0, 0, 0, 0, 0 }
    };

    logMessage("kickstartFromUrl");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksUrlOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt(*flagsPtr);
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
    if (strstr(url, "http://"))
	loaderData->method = strdup("http");
    else if (strstr(url, "ftp://"))
	loaderData->method = strdup("ftp");
    else {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        return;
    }

    loaderData->methodData = calloc(sizeof(struct urlInstallData *), 1);
    ((struct urlInstallData *)loaderData->methodData)->url = url;

    logMessage("results of url ks, url %s", url);
}

