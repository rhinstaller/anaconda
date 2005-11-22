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

#include "../isys/imount.h"

int nfsGetSetup(char ** hostptr, char ** dirptr) {
    struct newtWinEntry entries[3];
    char * buf;
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = (const char **) &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;
    entries[1].text = sdupprintf(_("%s directory:"), getProductName());
    entries[1].value = (const char **) &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = NULL;
    entries[2].value = NULL;
    buf = sdupprintf(_(netServerPrompt), "NFS", getProductName());
    rc = newtWinEntries(_("NFS Setup"), buf, 60, 5, 15,
                        24, entries, _("OK"), _("Back"), NULL);
    free(buf);

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
                     moduleDeps * modDepsPtr, int flags) {
    char * host = NULL;
    char * directory = NULL;
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
            if (loaderData->method && *loaderData->method &&
                !strncmp(loaderData->method, "nfs", 3) &&
                loaderData->methodData) {
                host = ((struct nfsInstallData *)loaderData->methodData)->host;
                directory = ((struct nfsInstallData *)loaderData->methodData)->directory;

                logMessage(INFO, "host is %s, dir is %s", host, directory);

                if (!host || !directory) {
                    logMessage(ERROR, "missing host or directory specification");
                    free(loaderData->method);
                    loaderData->method = NULL;
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
            struct in_addr ip;

            if (loaderData->noDns && !(inet_aton(host, &ip))) {
                newtWinMessage(_("Error"), _("OK"),
                               _("Hostname specified with no DNS configured"));
                if (loaderData->method) {
                    free(loaderData->method);
                    loaderData->method = NULL;
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
                           IMOUNT_RDONLY, NULL)) {
		char mntPath[1024];

		snprintf(mntPath, sizeof(mntPath), "/mnt/source/%s/base/stage2.img", getProductPath());
                if (!access(mntPath, R_OK)) {
                    logMessage(INFO, "can access %s", mntPath);
                    rc = mountStage2(mntPath);
                    logMessage(DEBUGLVL, "after mountStage2, rc is %d", rc);
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
                    logMessage(WARNING, "unable to access %s", mntPath);
                }

                if ((path = validIsoImages("/mnt/source", &foundinvalid))) {
		    foundinvalid = 0;
		    logMessage(INFO, "Path to valid iso is %s", path);
                    copyUpdatesImg("/mnt/source/updates.img");

                    if (mountLoopback(path, "/mnt/source2", "loop1")) 
                        logMessage(WARNING, "failed to mount iso %s loopback", path);
                    else {
			snprintf(mntPath, sizeof(mntPath), "/mnt/source2/%s/base/stage2.img", getProductPath());
                        rc = mountStage2(mntPath);
                        if (rc) {
                            umountLoopback("/mnt/source2", "loop1");
                            if (rc == -1)
				foundinvalid = 1;
                        } else {
                            /* JKFIXME: hack because /mnt/source is hard-coded
                             * in mountStage2() */
			    snprintf(mntPath, sizeof(mntPath), "/mnt/source2/%s/base/updates.img", getProductPath());
                            copyUpdatesImg(mntPath);
			    snprintf(mntPath, sizeof(mntPath), "/mnt/source2/%s/base/product.img", getProductPath());
                            copyProductImg(mntPath);

                            queryIsoMediaCheck(path, flags);

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
                    buf = sdupprintf(_("The %s installation tree in that "
                                       "directory does not seem to match "
                                       "your boot media."), getProductName());
                else
                    buf = sdupprintf(_("That directory does not seem to "
                                       "contain a %s installation tree."),
                                     getProductName());
                newtWinMessage(_("Error"), _("OK"), buf);
                if (loaderData->method) {
                    free(loaderData->method);
                    loaderData->method = NULL;
                }

		
                break;
            } else {
                newtWinMessage(_("Error"), _("OK"),
                               _("That directory could not be mounted from "
                                 "the server."));
                if (loaderData->method) {
                    free(loaderData->method);
                    loaderData->method = NULL;
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
                     char ** argv, int * flagsPtr) {
    char * host = NULL, * dir = NULL;
    poptContext optCon;
    int rc;
    struct poptOption ksNfsOptions[] = {
        { "server", '\0', POPT_ARG_STRING, &host, 0, NULL, NULL },
        { "dir", '\0', POPT_ARG_STRING, &dir, 0, NULL, NULL },
        { 0, 0, 0, 0, 0, 0, 0 }
    };

    logMessage(INFO, "kickstartFromNfs");
    optCon = poptGetContext(NULL, argc, (const char **) argv, ksNfsOptions, 0);
    if ((rc = poptGetNextOpt(optCon)) < -1) {
        startNewt(*flagsPtr);
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

    loaderData->method = strdup("nfs");
    loaderData->methodData = calloc(sizeof(struct nfsInstallData *), 1);
    if (host)
        ((struct nfsInstallData *)loaderData->methodData)->host = host;
    if (dir)
        ((struct nfsInstallData *)loaderData->methodData)->directory = dir;

    logMessage(INFO, "results of nfs, host is %s, dir is %s", host, dir);
}


int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData, 
                   int flags) {
    char * host = NULL, *path = NULL, * file = NULL;
    int failed = 0;
    struct networkDeviceConfig netCfg;

    if (kickstartNetworkUp(loaderData, &netCfg, flags)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    /* if they just did 'linux ks', they want us to figure it out from
     * the dhcp/bootp information
     */
    if (url == NULL) {
        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_NEXTSERVER)) {
            logMessage(ERROR, "no bootserver was found");
            return 1;
        }
         
        if (!(netCfg.dev.set & PUMP_INTFINFO_HAS_BOOTFILE)) {
            url = sdupprintf("%s:%s", inet_ntoa(netCfg.dev.nextServer),
                             "/kickstart/");
            logMessage(ERROR, "bootp: no bootfile received");
        } else {
            url = sdupprintf("%s:%s", inet_ntoa(netCfg.dev.nextServer),
                             netCfg.dev.bootFile);
        }
    } 
      
    logMessage(INFO, "url is %s", url);

    getHostandPath(url, &host, &path, inet_ntoa(netCfg.dev.ip));

    /* nfs has to be a little bit different... split off the last part as
     * the file and then concatenate host + dir path */
    file = strrchr(path, '/');
    if (!file) {
        file = path;
    } else {
        *file++ ='\0';
        host = sdupprintf("%s/%s", host, path);
    }

    logMessage(INFO, "file location: nfs://%s/%s", host, file);

    if (!doPwMount(host, "/tmp/mnt", "nfs", IMOUNT_RDONLY, NULL)) {
        char * buf;

        buf = alloca(strlen(file) + 10);
        sprintf(buf, "/tmp/mnt/%s", file);
        if (copyFile(buf, dest)) {
            logMessage(ERROR, "failed to copy file to %s", dest);
            failed = 1;
        }
        
    } else {
        logMessage(ERROR, "failed to mount nfs source");
        failed = 1;
    }

    umount("/tmp/mnt");
    unlink("/tmp/mnt");

    return failed;
}

int kickstartFromNfs(char * url, struct loaderData_s * loaderData, 
                     int flags) {
    return getFileFromNfs(url, "/tmp/ks.cfg", loaderData, flags);    
}
