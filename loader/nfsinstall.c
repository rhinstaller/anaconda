/*
 * nfsinstall.c - code to set up nfs installs
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005,
 * 2006, 2007  Red Hat, Inc.  All rights reserved.
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

#include <fcntl.h>
#include <newt.h>
#include <popt.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>

#include "copy.h"
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
#include "../isys/iface.h"

/* boot flags */
extern uint64_t flags;

static int nfsGetSetup(char ** hostptr, char ** dirptr) {
    struct newtWinEntry entries[3];
    char * buf;
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;

    if (asprintf(&entries[1].text, _("%s directory:"),
                 getProductName()) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    entries[1].value = &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = NULL;
    entries[2].value = NULL;

    if (asprintf(&buf, _("Please enter the server name and path to your %s "
                         "installation image."), getProductName()) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    do {
        rc = newtWinEntries(_("NFS Setup"), buf, 60, 5, 15,
                            24, entries, _("OK"), _("Back"), NULL);
    } while (!strcmp(newServer, "") || !strcmp(newDir, ""));

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
                     char * location, struct loaderData_s * loaderData) {
    char * host = NULL;
    char * directory = NULL;
    char * mountOpts = NULL;
    char * fullPath = NULL;
    char * url = NULL;

    enum { NFS_STAGE_NFS, NFS_STAGE_MOUNT, NFS_STAGE_DONE,
           NFS_STAGE_UPDATES } stage = NFS_STAGE_NFS;

    int rc;

    /* JKFIXME: ASSERT -- we have a network device setup when we get here */
    while (stage != NFS_STAGE_DONE) {
        switch (stage) {
        case NFS_STAGE_NFS:
            logMessage(INFO, "going to do nfsGetSetup");
            if (loaderData->method == METHOD_NFS && loaderData->stage2Data) {
                host = ((struct nfsInstallData *)loaderData->stage2Data)->host;
                directory = ((struct nfsInstallData *)loaderData->stage2Data)->directory;

                if (((struct nfsInstallData *)
                    loaderData->stage2Data)->mountOpts == NULL) {
                    mountOpts = strdup("ro");
                } else {
                    if (asprintf(&mountOpts, "ro,%s",
                                 ((struct nfsInstallData *)
                                 loaderData->stage2Data)->mountOpts) == -1) {
                        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                        abort();
                    }
                }

                logMessage(INFO, "host is %s, dir is %s, opts are '%s'", host, directory, mountOpts);

                if (!host || !directory) {
                    logMessage(ERROR, "missing host or directory specification");

                    if (loaderData->inferredStage2)
                        loaderData->invalidRepoParam = 1;

                    loaderData->method = -1;
                    break;
                } else {
                    host = strdup(host);
                    directory = strdup(directory);
                }
            } else {
                char *substr, *tmp;

                if (nfsGetSetup(&host, &directory) == LOADER_BACK)
                    return NULL;

                /* If the user-provided URL points at a repo instead of a
                 * stage2 image, fix that up now.
                 */
                substr = strstr(directory, ".img");
                if (!substr || (substr && *(substr+4) != '\0')) {
                    if (asprintf(&(loaderData->instRepo), "nfs:%s:%s",
                                 host, directory) == -1) {
                        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                        abort();
                    }

                    if (asprintf(&tmp, "nfs:%s:%s/images/install.img",
                                 host, directory) == -1) {
                        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                        abort();
                    }

                    setStage2LocFromCmdline(tmp, loaderData);
                    free(host);
                    free(directory);
                    free(tmp);
                    continue;
                }

                loaderData->invalidRepoParam = 1;
            }

            stage = NFS_STAGE_MOUNT;
            break;

        case NFS_STAGE_MOUNT: {
            char *buf;

            if (asprintf(&fullPath, "%s:%.*s", host,
                         (int) (strrchr(directory, '/')-directory),
                         directory) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            logMessage(INFO, "mounting nfs path %s", fullPath);

            if (FL_TESTING(flags)) {
                stage = NFS_STAGE_DONE;
                break;
            }

            stage = NFS_STAGE_NFS;

            if (!doPwMount(fullPath, "/mnt/stage2", "nfs", mountOpts, NULL)) {
                if (asprintf(&buf, "/mnt/stage2/%s",
                             strrchr(directory, '/')) == -1) {
                    logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                    abort();
                }

                if (!access(buf, R_OK)) {
                    logMessage(INFO, "can access %s", buf);
                    rc = mountStage2(buf);

                    if (rc == 0) {
                        stage = NFS_STAGE_UPDATES;

                        if (asprintf(&url, "nfs:%s:%s", host,
                                     directory) == -1) {
                            logMessage(CRITICAL, "%s: %d: %m", __func__,
                                       __LINE__);
                            abort();
                        }

                        free(buf);
                        break;
                    } else {
                        logMessage(WARNING, "unable to mount %s", buf);
                        free(buf);
                        break;
                    }
                } else {
                    logMessage(WARNING, "unable to access %s", buf);
                    free(buf);
                    umount("/mnt/stage2");
                }
            } else {
                newtWinMessage(_("Error"), _("OK"),
                               _("That directory could not be mounted from "
                                 "the server."));
                if (loaderData->method >= 0)
                    loaderData->method = -1;

                if (loaderData->inferredStage2)
                    loaderData->invalidRepoParam = 1;

                break;
            }

            if (asprintf(&buf, _("That directory does not seem to "
                                 "contain a %s installation image."),
                         getProductName()) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            newtWinMessage(_("Error"), _("OK"), buf);
            free(buf);

            if (loaderData->method >= 0)
                loaderData->method = -1;

            if (loaderData->inferredStage2)
                loaderData->invalidRepoParam = 1;

            break;
        }

        case NFS_STAGE_UPDATES: {
            char *buf;

            if (asprintf(&buf, "%.*s/RHupdates",
                         (int) (strrchr(fullPath, '/')-fullPath),
                         fullPath) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            logMessage(INFO, "mounting nfs path %s for updates", buf);

            if (!doPwMount(buf, "/tmp/update-disk", "nfs", mountOpts, NULL)) {
                logMessage(INFO, "Using RHupdates/ for NFS install");
                copyDirectory("/tmp/update-disk", "/tmp/updates", NULL, NULL);
                umount("/tmp/update-disk");
                unlink("/tmp/update-disk");
            } else {
                logMessage(INFO, "No RHupdates/ directory found, skipping");
            }

            stage = NFS_STAGE_DONE;
            break;
        }

        case NFS_STAGE_DONE:
            break;
        }
    }

    free(host);
    free(directory);
    if (fullPath)
        free(fullPath);

    return url;
}


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char * host = NULL, * dir = NULL, * mountOpts = NULL;
    char *substr = NULL;
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

    substr = strstr(dir, ".img");
    if (!substr || (substr && *(substr+4) != '\0')) {
        if (mountOpts) {
            if (asprintf(&(loaderData->instRepo), "nfs:%s:%s:%s", host, dir, mountOpts) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }
        } else {
            if (asprintf(&(loaderData->instRepo), "nfs:%s:%s", host, dir) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }
        }

        logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'",
                   host, dir, mountOpts);
    } else {
        loaderData->stage2Data = calloc(sizeof(struct nfsInstallData *), 1);
        ((struct nfsInstallData *)loaderData->stage2Data)->host = host;
        ((struct nfsInstallData *)loaderData->stage2Data)->directory = dir;
        ((struct nfsInstallData *)loaderData->stage2Data)->mountOpts = mountOpts;

        logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'",
                   ((struct nfsInstallData *) loaderData->stage2Data)->host,
                   ((struct nfsInstallData *) loaderData->stage2Data)->directory,
                   ((struct nfsInstallData *) loaderData->stage2Data)->mountOpts);
    }
}


int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData) {
    char * host = NULL, *path = NULL, * file = NULL, * opts = NULL;
    char * chk = NULL, *ip = NULL;
    int failed = 0;
    iface_t iface;

    if (kickstartNetworkUp(loaderData, &iface)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    /* if they just did 'linux ks', they want us to figure it out from
     * the dhcp/bootp information
     */
/* XXX: fixme NetworkManager integration */
/*
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

            if (asprintf(&url, "%s:%s", ret, "/kickstart/") == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            logMessage(ERROR, "bootp: no bootfile received");
        } else {
            inet_ntop(tip->sa_family, IP_ADDR(tip), ret, IP_STRLEN(tip));

            if (asprintf(&url, "%s:%s", ret, netCfg.dev.bootFile) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }

            logMessage(INFO, "bootp: bootfile is %s", netCfg.dev.bootFile);
        }
    }
*/

    /* get the IP of the target system */
    if ((ip = iface_ip2str(loaderData->netDev, AF_INET)) == NULL) {
        logMessage(ERROR, "nl_ip2str returned NULL");
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

        if (*chk == '/' || *path == '/') {
            if (asprintf(&host, "%s%s", host, path) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }
        } else {
            if (asprintf(&host, "%s/%s", host, path) == -1) {
                logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
                abort();
            }
        }
    }

    logMessage(INFO, "file location: nfs:%s/%s", host, file);

    if (!doPwMount(host, "/tmp/mnt", "nfs", opts, NULL)) {
        char * buf;

        if (asprintf(&buf, "/tmp/mnt/%s", file) == -1) {
            logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
            abort();
        }

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
