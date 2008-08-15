/*
 * nfsinstall.c - code to set up nfs installs
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

#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "loader.h"
#include "lang.h"
#include "loadermisc.h"
#include "kickstart.h"
#include "log.h"
#include "method.h"
#include "nfsinstall.h"
#include "net.h"
#include "cdinstall.h"
#include "windows.h"

#include "../isys/imount.h"
#include "../isys/nl.h"

/* boot flags */
extern uint64_t flags;

int nfsGetSetup(char ** hostptr, char ** dirptr) {
    struct newtWinEntry entries[3];
    char * buf;
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = (const char **) &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;
    rc = asprintf(&entries[1].text, _("%s directory:"), getProductName());
    entries[1].value = (const char **) &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = NULL;
    entries[2].value = NULL;
    rc = asprintf(&buf, _(netServerPrompt), _("NFS"), getProductName());
    rc = newtWinEntries(_("NFS Setup"), buf, 60, 5, 15,
                        24, entries, _("OK"), _("Back"), NULL);
    free(buf);
    free(entries[1].text);

    if (rc == 2) {
        if (newServer) free(newServer);
        if (newDir) free(newDir);
        return LOADER_BACK;
    }

    if (*hostptr) free(*hostptr);
    if (*dirptr) free(*dirptr);
    *hostptr = newServer;
    *dirptr = newDir;

    return 0;
}

char * mountNfsImage(struct installMethod * method,
                     char * location, struct loaderData_s * loaderData,
                     moduleInfoSet modInfo, moduleList modLoaded,
                     moduleDeps * modDepsPtr) {
    char * host = NULL;
    char * directory = NULL;
    char * mountOpts = NULL;
    char * fullPath = NULL;
    char * path;
    char * url = NULL;

    enum { NFS_STAGE_NFS, NFS_STAGE_MOUNT, 
           NFS_STAGE_DONE } stage = NFS_STAGE_NFS;

    int rc;
    int dir = 1;

    /* JKFIXME: ASSERT -- we have a network device setup when we get here */
    while (stage != NFS_STAGE_DONE) {
        switch (stage) {
        case NFS_STAGE_NFS:
            logMessage(INFO, "going to do nfsGetSetup");
            if (loaderData->method == METHOD_NFS && loaderData->methodData) {
                host = ((struct nfsInstallData *)loaderData->methodData)->host;
                directory = ((struct nfsInstallData *)loaderData->methodData)->directory;
                mountOpts = ((struct nfsInstallData *)loaderData->methodData)->mountOpts;

                logMessage(INFO, "host is %s, dir is %s, opts are '%s'", host, directory, mountOpts);

                if (!host || !directory) {
                    logMessage(ERROR, "missing host or directory specification");
                    loaderData->method = -1;
                    break;
                } else {
                    host = strdup(host);
                    directory = strdup(directory);
                }
            } else if (nfsGetSetup(&host, &directory) == LOADER_BACK) {
                return NULL;
            }
             
            stage = NFS_STAGE_MOUNT;
            dir = 1;
            break;

        case NFS_STAGE_MOUNT: {
            int foundinvalid = 0;
            char * buf;
            char * cdurl;
            struct in_addr ip;

            if (loaderData->noDns && !(inet_pton(AF_INET, host, &ip))) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Hostname specified with no DNS configured"));
                if (loaderData->method >= 0) {
                    loaderData->method = -1;
                }
                break;
            }

            fullPath = alloca(strlen(host) + strlen(directory) + 2);
            sprintf(fullPath, "%s:%s", host, directory);

            logMessage(INFO, "mounting nfs path %s", fullPath);

            if (FL_TESTING(flags)) {
                stage = NFS_STAGE_DONE;
                dir = 1;
                break;
            }

            stage = NFS_STAGE_NFS;

            if (!doPwMount(fullPath, "/mnt/source", "nfs", 
                           IMOUNT_RDONLY, mountOpts)) {
                if (!access("/mnt/source/images/stage2.img", R_OK)) {
                    logMessage(INFO, "can access /mnt/source/images/stage2.img");
                    /* try to see if we're booted off of a CD with stage2 */
                    cdurl = findAnacondaCD("/mnt/stage2", modInfo, modLoaded, *modDepsPtr, 0);
                    if (cdurl) {
                        logMessage(INFO, "Detected stage 2 image on CD");
                        winStatus(50, 3, _("Media Detected"),
                                  _("Local installation media detected..."), 0);
                        sleep(3);
                        newtPopWindow();
                        rc = 0;
                    } else {
                        rc = mountStage2("/mnt/source/images/stage2.img");
                        logMessage(DEBUGLVL, "after mountStage2, rc is %d", rc);
                    }
                    if (rc) {
                        if (rc == -1) { 
                            foundinvalid = 1; 
                            logMessage(WARNING, "not the right one"); 
                        }
                    } else {
                        stage = NFS_STAGE_DONE;
                        url = "nfs://mnt/source/.";
                        break;
                    }
                } else {
                    logMessage(WARNING, "unable to access /mnt/source/images/stage2.img");
                }

                if ((path = validIsoImages("/mnt/source", &foundinvalid))) {
		    foundinvalid = 0;
		    logMessage(INFO, "Path to valid iso is %s", path);
                    copyUpdatesImg("/mnt/source/updates.img");

                    if (mountLoopback(path, "/mnt/source2", "loop1")) 
                        logMessage(WARNING, "failed to mount iso %s loopback", path);
                    else {
                        /* try to see if we're booted off of a CD with stage2 */
                        cdurl = findAnacondaCD("/mnt/stage2", modInfo, modLoaded, *modDepsPtr, 0);
                        if (cdurl) {
                            logMessage(INFO, "Detected stage 2 image on CD");
                            winStatus(50, 3, _("Media Detected"),
                                      _("Local installation media detected..."), 0);
                            sleep(3);
                            newtPopWindow();
                            rc = 0;
                        } else {
                            rc = mountStage2("/mnt/source2/images/stage2.img");
                        }
                        if (rc) {
                            umountLoopback("/mnt/source2", "loop1");
                            if (rc == -1)
				foundinvalid = 1;
                        } else {
                            /* JKFIXME: hack because /mnt/source is hard-coded
                             * in mountStage2() */
                            copyUpdatesImg("/mnt/source2/images/updates.img");
                            copyProductImg("/mnt/source2/images/product.img");

                            queryIsoMediaCheck(path);

                            stage = NFS_STAGE_DONE;
                            url = "nfsiso:/mnt/source";
                            break;
                        }
                    }
                }

		/* if we fell through to here we did not find a valid NFS */
		/* source for installation.                               */
		umount("/mnt/source");
                if (foundinvalid) 
                    rc = asprintf(&buf, _("The %s installation tree in that "
                                     "directory does not seem to match "
                                     "your boot media."), getProductName());
                else
                    rc = asprintf(&buf, _("That directory does not seem to "
                                     "contain a %s installation tree."),
                                   getProductName());
                newtWinMessage(_("Error"), _("OK"), buf);
                free(buf);
                if (loaderData->method >= 0) {
                    loaderData->method = -1;
                }

		
                break;
            } else {
                newtWinMessage(_("Error"), _("OK"),
                               _("That directory could not be mounted from "
                                 "the server."));
                if (loaderData->method >= 0) {
                    loaderData->method = -1;
                }
                break;
            }
        }

        case NFS_STAGE_DONE:
            break;
        }
    }

    free(host);
    free(directory);

    return url;
}


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char * host = NULL, * dir = NULL, * mountOpts = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksNfsOptions[] = {
        { "server", '\0', POPT_ARG_STRING, &host, 0, NULL, NULL },
        { "dir", '\0', POPT_ARG_STRING, &dir, 0, NULL, NULL },
        { "opts", '\0', POPT_ARG_STRING, &mountOpts, 0, NULL, NULL},
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    logMessage(INFO, "kickstartFromNfs");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksNfsOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to NFS kickstart method "
                         "command %s: %s"),
                       poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
                       poptStrerror(rc));
        return;
    }

    if (!host || !dir) {
        logMessage(ERROR, "host and directory for nfs kickstart not specified");
        return;
    }

    loaderData->method = METHOD_NFS;
    loaderData->methodData = calloc(sizeof(struct nfsInstallData *), 1);
    if (host)
        ((struct nfsInstallData *)loaderData->methodData)->host = host;
    if (dir)
        ((struct nfsInstallData *)loaderData->methodData)->directory = dir;
    if (mountOpts)
        ((struct nfsInstallData *)loaderData->methodData)->mountOpts = mountOpts;

    logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'", host, dir, mountOpts);
}


int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData) {
    char * host = NULL, *path = NULL, * file = NULL, * opts = NULL;
    char * chk = NULL, *ip = NULL;
    int failed = 0;
    int i;
    struct networkDeviceConfig netCfg;

    if (kickstartNetworkUp(loaderData, &netCfg)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    /* if they just did 'linux ks', they want us to figure it out from
     * the dhcp/bootp information
     */
    if (url == NULL) {
        char ret[47];
        ip_addr_t *tip;

        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_NEXTSERVER)) {
            logMessage(ERROR, "no bootserver was found");
            return 1;
        }

        tip = &(netCfg.dev.nextServer);
        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_BOOTFILE)) {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            i = asprintf(&url, "%s:%s", ret, "/kickstart/");
            logMessage(ERROR, "bootp: no bootfile received");
        } else {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));
            i = asprintf(&url, "%s:%s", ret, netCfg.dev.bootFile);
            logMessage(INFO, "bootp: bootfile is %s", netCfg.dev.bootFile);
        }
    }

    /* get the IP of the target system */
    netlink_init_interfaces_list();
    if ((ip = netlink_interfaces_ip2str(loaderData->netDev)) == NULL) {
        logMessage(ERROR, "netlink_interfaces_ip2str returned NULL");
        return 1;
    }

    logMessage(INFO, "url is %s", url);
    getHostandPath(url, &host, &path, ip);

    opts = strchr(host, ':');
    if (opts && (strlen(opts) > 1)) {
        char * c = opts;
        opts = host;
        host = c + 1;
        *c = '\0';
    } else {
        opts = NULL;
    }

    /* nfs has to be a little bit different... split off the last part as
     * the file and then concatenate host + dir path */
    file = strrchr(path, '/');
    if (!file) {
        file = path;
    } else {
        *file++ ='\0';
        chk = host + strlen(host)-1;

        if (*chk == '/' || *path == '/')
            i = asprintf(&host, "%s%s", host, path);
        else
            i = asprintf(&host, "%s/%s", host, path);
    }

    logMessage(INFO, "file location: nfs://%s/%s", host, file);

    if (!doPwMount(host, "/tmp/mnt", "nfs", IMOUNT_RDONLY, opts)) {
        char * buf;

        i = asprintf(&buf, "/tmp/mnt/%s", file);
        if (copyFile(buf, dest)) {
            logMessage(ERROR, "failed to copy file to %s", dest);
            failed = 1;
        }

        free(buf);
    } else {
        logMessage(ERROR, "failed to mount nfs source");
        failed = 1;
    }

    free(host);
    free(path);
    if (ip) free(ip);

    umount("/tmp/mnt");
    unlink("/tmp/mnt");

    return failed;
}

int kickstartFromNfs(char * url, struct loaderData_s * loaderData) {
    return getFileFromNfs(url, "/tmp/ks.cfg", loaderData);
}

/* vim:set shiftwidth=4 softtabstop=4: */
