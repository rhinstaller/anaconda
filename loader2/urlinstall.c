/*
 * urlinstall.c - code to set up url (ftp/http) installs
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

#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "log.h"
#include "method.h"
#include "net.h"
#include "method.h"
#include "urls.h"

static int loadSingleUrlImage(struct iurlinfo * ui, char * file, int flags, 
			char * dest, char * mntpoint, char * device,
			int silentErrors) {
    int fd;
    int rc;
    char * newFile = NULL;

    fd = urlinstStartTransfer(ui, file, 1);

    if (fd == -2) return 1;

    if (fd < 0) {
        /* file not found */

        newFile = alloca(strlen(device) + 20);
        sprintf(newFile, "disc1/%s", file);

        fd = urlinstStartTransfer(ui, newFile, 1);

        if (fd == -2) return 1;
        if (fd < 0) {
            if (!silentErrors) 
                newtWinMessage(_("Error"), _("OK"),
                               _("File %s/%s not found on server."), 
                               ui->prefix, file);
            return 1;
        }
    }

    rc = copyFileAndLoopbackMount(fd, dest, flags, device, mntpoint);

    urlinstFinishTransfer(ui, fd);

    if (newFile) {
        newFile = malloc(strlen(ui->prefix ) + 20);
        sprintf(newFile, "%s/disc1", ui->prefix);
        free(ui->prefix);
        ui->prefix = newFile;
    }

    return rc;
}


static int loadUrlImages(struct iurlinfo * ui, int flags) {
    setupRamdisk();

    /* grab the updates.img before netstg1.img so that we minimize our
     * ramdisk usage */
    if (!loadSingleUrlImage(ui, "RedHat/base/updates.img", flags,
                            "/tmp/ramfs/updates-disk.img", "/tmp/update-disk",
                            "loop7", 1)) {
        copyDirectory("/tmp/update-disk", "/tmp/updates");
        umountLoopback("/tmp/update-disk", "loop7");
        unlink("/tmp/ramfs/updates-disk.img");
    }

    if (loadSingleUrlImage(ui, "RedHat/base/netstg1.img", flags,
                           "/tmp/ramfs/netstg1.img",
                           "/mnt/runtime", "loop0", 0)) {
        newtWinMessage(_("Error"), _("OK"),
                       _("Unable to retrieve the install image."));
        return 1;
    }

    /* now verify the stamp... */
    if (!verifyStamp("/mnt/runtime")) {
	char * buf;

	buf = sdupprintf(_("The %s installation tree in that directory does "
			   "not seem to match your boot media."), PRODUCTNAME);

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
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDeps, int flags) {
    int rc;
    char * url;
    char * devName;
    static struct networkDeviceConfig netDev;
    struct iurlinfo ui;
    char needsSecondary = ' ';
    int dir = 1;
    char * login;
    char * finalPrefix;

    enum { URL_STAGE_IFACE, URL_STAGE_IP, URL_STAGE_MAIN, URL_STAGE_SECOND, 
           URL_STAGE_FETCH, URL_STAGE_DONE } stage = URL_STAGE_IFACE;

    enum urlprotocol_t proto = 
        !strcmp(method->name, "FTP") ? URL_METHOD_FTP : URL_METHOD_HTTP;

    /* JKFIXME: we used to do another ram check here... keep it? */

    initLoopback();

    memset(&ui, 0, sizeof(ui));
    memset(&netDev, 0, sizeof(netDev));
    netDev.isDynamic = 1;

    while (stage != URL_STAGE_DONE) {
        switch(stage) {
        case URL_STAGE_IFACE:
            logMessage("going to pick interface");
            rc = chooseNetworkInterface(kd, &devName, flags);
            if ((rc == LOADER_BACK) || (rc == LOADER_ERROR) ||
                ((dir == -1) && (rc == LOADER_NOOP))) return NULL;
            
            stage = URL_STAGE_IP;
            dir = 1;
            break;

        case URL_STAGE_IP:
            logMessage("going to do getNetConfig");
            rc = readNetConfig(devName, &netDev, flags);
            if (rc) {
                stage = URL_STAGE_IFACE;
                dir = -1;
                break;
            }
            stage = URL_STAGE_MAIN;
            dir = 1;

        case URL_STAGE_MAIN:
            rc = urlMainSetupPanel(&ui, proto, &needsSecondary);
            if (rc) {
                stage = URL_STAGE_IP;
                dir = -1;
            } else { 
                stage = (needsSecondary != ' ') ? URL_STAGE_SECOND : 
                    URL_STAGE_FETCH;
                dir = 1;
            }
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

    sprintf(url, "%s://%s%s/%s", 
	    ui.protocol == URL_METHOD_FTP ? "ftp" : "http",
	    login, ui.address, finalPrefix);
    writeNetInfo("/tmp/netinfo", &netDev, kd);

    return url;
}
