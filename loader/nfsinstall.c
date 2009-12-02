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
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <glib.h>
#include <nm-client.h>
#include <nm-device.h>
#include <nm-dhcp4-config.h>

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

static int nfsGetSetup(char ** hostptr, char ** dirptr, char ** optsptr) {
    struct newtWinEntry entries[4];
    char * buf;
    char * newServer = *hostptr ? strdup(*hostptr) : NULL;
    char * newDir = *dirptr ? strdup(*dirptr) : NULL;
    char * newMountOpts = *optsptr ? strdup(*optsptr) : NULL;
    int rc;

    entries[0].text = _("NFS server name:");
    entries[0].value = &newServer;
    entries[0].flags = NEWT_FLAG_SCROLL;
    
    checked_asprintf(&entries[1].text, _("%s directory:"), getProductName());

    entries[1].value = &newDir;
    entries[1].flags = NEWT_FLAG_SCROLL;
    entries[2].text = _("NFS mount options (optional):");
    entries[2].value = &newMountOpts;
    entries[2].flags = NEWT_FLAG_SCROLL;
    entries[3].text = NULL; 
    entries[3].value = NULL;

    if (asprintf(&buf, _("Please enter the server and path to your %s "
                         "installation image and optionally additional "
                         "NFS mount options."), getProductName()) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    do {
        rc = newtWinEntries(_("NFS Setup"), buf, 60, 5, 15,
                            24, entries, _("OK"), _("Back"), NULL);
    } while ((!strcmp(newServer, "") || !strcmp(newDir, "")) && rc != 2);

    free(buf);
    free(entries[1].text);

    if (rc == 2) {
        if (newServer) free(newServer);
        if (newDir) free(newDir);
        if (newMountOpts) free(newMountOpts);
        return LOADER_BACK;
    }

    if (*hostptr) free(*hostptr);
    if (*dirptr) free(*dirptr);
    if (*optsptr) free(*optsptr);
    *hostptr = newServer;
    *dirptr = newDir;
    *optsptr = newMountOpts;

    return 0;
}

void parseNfsHostPathOpts(char *url, char **host, char **path, char **opts) {
    char *tmp;
    char *hostsrc;

    logMessage(DEBUGLVL, "parseNfsHostPathOpts url: |%s|", url);

    hostsrc = strdup(url);
    *host = hostsrc;
    tmp = strchr(*host, ':');

    if (tmp) {
       *path = strdup(tmp + 1);
       *tmp = '\0';
    }
    else {
        *path = malloc(sizeof(char *));
        **path = '\0';
    }

    tmp = strchr(*path, ':');
    if (tmp && (strlen(tmp) > 1)) {
	char * c = tmp;
        *opts = *host;
        *host = *path;
	*path = strdup(c + 1);
	*c = '\0';
    } else {
	*opts = NULL;
    }

    logMessage(DEBUGLVL, "parseNfsHostPathOpts host: |%s|", *host);
    logMessage(DEBUGLVL, "parseNfsHostPathOpts path: |%s|", *path);
    logMessage(DEBUGLVL, "parseNfsHostPathOpts opts: |%s|", *opts);
}

static void addDefaultKickstartFile(char **file, char *ip) {
    /* if the filename ends with / or is null, use default kickstart
     * name of IP_ADDRESS-kickstart appended to *file
     */
    if ((*file) && (((*file)[strlen(*file) - 1] == '/') ||
                    ((*file)[strlen(*file) - 1] == '\0'))) {
        checked_asprintf(file, "%s%s-kickstart", *file, ip);
        logMessage(DEBUGLVL, "addDefaultKickstartFile file: |%s|", *file);
    }
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
            if (loaderData->method == METHOD_NFS && loaderData->stage2Data) {
                host = ((struct nfsInstallData *)loaderData->stage2Data)->host;
                directory = ((struct nfsInstallData *)loaderData->stage2Data)->directory;

                if (((struct nfsInstallData *)
                    loaderData->stage2Data)->mountOpts == NULL) {
                    mountOpts = strdup("ro");
                } else {
                    checked_asprintf(&mountOpts, "ro,%s",
                                     ((struct nfsInstallData *)
                                      loaderData->stage2Data)->mountOpts);
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
                char *colonopts, *substr, *tmp;

                logMessage(INFO, "going to do nfsGetSetup");
                if (nfsGetSetup(&host, &directory, &mountOpts) == LOADER_BACK) {
                    loaderData->stage2Data = NULL;
                    return NULL;
                }

                /* If the user-provided URL points at a repo instead of a
                 * stage2 image, fix that up now.
                 */
                substr = strstr(directory, ".img");
                if (!substr || (substr && *(substr+4) != '\0')) {
                    if (mountOpts && strlen(mountOpts)) {
                        checked_asprintf(&colonopts, ":%s", mountOpts);
                    } else {
                        colonopts = strdup("");
                    }

                    checked_asprintf(&(loaderData->instRepo), "nfs%s:%s:%s",
                                     colonopts, host, directory);
                    checked_asprintf(&tmp, "nfs%s:%s:%s/images/install.img",
                                     colonopts, host, directory);

                    setStage2LocFromCmdline(tmp, loaderData);
                    free(host);
                    free(directory);
                    free(mountOpts);
                    free(colonopts);
                    free(tmp);
                    continue;
                }

                loaderData->invalidRepoParam = 1;
            }

            stage = NFS_STAGE_MOUNT;
            break;

        case NFS_STAGE_MOUNT: {
            char *buf;

            checked_asprintf(&fullPath, "%s:%.*s", host,
                             (int) (strrchr(directory, '/')-directory),
                             directory);
            logMessage(INFO, "mounting nfs path %s", fullPath);

            stage = NFS_STAGE_NFS;

            if (!doPwMount(fullPath, "/mnt/stage2", "nfs", mountOpts, NULL)) {
                checked_asprintf(&buf, "/mnt/stage2/%s",
                                 strrchr(directory, '/'));

                if (!access(buf, R_OK)) {
                    logMessage(INFO, "can access %s", buf);
                    rc = mountStage2(buf);

                    if (rc == 0) {
                        stage = NFS_STAGE_UPDATES;
                        checked_asprintf(&url, "nfs:%s:%s", host,
                                         directory);
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

            checked_asprintf(&buf,
                             _("That directory does not seem to "
                               "contain a %s installation image."),
                             getProductName());

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

            checked_asprintf(&buf, "%.*s/RHupdates",
                             (int) (strrchr(fullPath, '/')-fullPath),
                             fullPath);

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
    if (mountOpts)
        free(mountOpts);
    if (fullPath)
        free(fullPath);

    return url;
}


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char *substr = NULL;
    gchar *host = NULL, *dir = NULL, *mountOpts = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksNfsOptions[] = {
        { "server", 0, 0, G_OPTION_ARG_STRING, &host, NULL, NULL },
        { "dir", 0, 0, G_OPTION_ARG_STRING, &dir, NULL, NULL },
        { "opts", 0, 0, G_OPTION_ARG_STRING, &mountOpts, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromNfs");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksNfsOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to NFS kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (!host || !dir) {
        logMessage(ERROR, "host and directory for nfs kickstart not specified");
        return;
    }

    loaderData->method = METHOD_NFS;
    loaderData->stage2Data = NULL;

    substr = strstr(dir, ".img");
    if (!substr || (substr && *(substr+4) != '\0')) {
        checked_asprintf(&(loaderData->instRepo), "nfs:%s:%s", host, dir);

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
    int failed = 0, i = 0;
    iface_t iface;
    NMClient *client = NULL;
    NMState state;
    const GPtrArray *devices;

    if (kickstartNetworkUp(loaderData, &iface)) {
        logMessage(ERROR, "unable to bring up network");
        return 1;
    }

    /* if they just did 'linux ks', they want us to figure it out from
     * the dhcp/bootp information
     */
    if (!url) {
        g_type_init();

        client = nm_client_new();
        if (!client) {
            logMessage(CRITICAL, "%s (%d): failure creating NM proxy",
                       __func__, __LINE__);
            return 1;
        }

        state = nm_client_get_state(client);
        if (state != NM_STATE_CONNECTED) {
            logMessage(ERROR, "%s (%d): no active network devices",
                       __func__, __LINE__);
            g_object_unref(client);
            return 1;
        }

        devices = nm_client_get_devices(client);
        for (i = 0; i < devices->len; i++) {
            NMDevice *candidate = g_ptr_array_index(devices, i);
            const char *devname = nm_device_get_iface(candidate);
            NMDHCP4Config *dhcp = NULL;
            const char *server_name = NULL;
            const char *filename = NULL;
            struct in_addr addr;
            char nextserver[INET_ADDRSTRLEN+1];

            if (nm_device_get_state(candidate) != NM_DEVICE_STATE_ACTIVATED)
                continue;

            if (strcmp(iface.device, devname))
                continue;

            dhcp = nm_device_get_dhcp4_config(candidate);
            if (!dhcp) {
                logMessage(ERROR, "no boot options received by DHCP");
                continue;
            }

            server_name = nm_dhcp4_config_get_one_option(dhcp, "server_name");
            if (!server_name) {
                logMessage(ERROR, "no bootserver was found");
                g_object_unref(client);
                return 1;
            }

            /* 'server_name' may be a hostname or an IPv4 address */
            memset(&nextserver, '\0', sizeof(nextserver));
            if (inet_pton(AF_INET, server_name, &addr) >= 1) {
                strcpy(nextserver, server_name);
            } else {
                struct hostent *he = gethostbyname(server_name);
                if (he != NULL) {
                    if (inet_ntop(AF_INET, he->h_addr_list[0],
                                  nextserver, INET_ADDRSTRLEN) == NULL) {
                        memset(&nextserver, '\0', sizeof(nextserver));
                    }
                }
            }

            filename = nm_dhcp4_config_get_one_option(dhcp, "filename");
            if (filename == NULL) {
                checked_asprintf(&url, "%s:/kickstart/", nextserver);
                logMessage(ERROR, "bootp: no bootfile received");
            } else {
                checked_asprintf(&url, "%s:%s", nextserver, filename);
                logMessage(INFO, "bootp: bootfile is %s", filename);
            }

            break;
        }

        g_object_unref(client);
    }

    /* get the IP of the target system */
    if ((ip = iface_ip2str(loaderData->netDev, AF_INET)) == NULL) {
        logMessage(ERROR, "iface_ip2str returned NULL");
        return 1;
    }

    logMessage(INFO, "url is %s", url);

    parseNfsHostPathOpts(url, &host, &path, &opts);
    addDefaultKickstartFile(&path, ip);

    /* nfs has to be a little bit different... split off the last part as
     * the file and then concatenate host + dir path */
    file = strrchr(path, '/');
    if (!file) {
        file = path;
    } else {
        *file++ ='\0';
        chk = host + strlen(host)-1;

        if (*chk == '/' || *path == '/') {
            checked_asprintf(&host, "%s:%s", host, path);
        } else {
            checked_asprintf(&host, "%s:/%s", host, path);
        }
    }

    logMessage(INFO, "file location: nfs:%s/%s", host, file);

    if (!doPwMount(host, "/tmp/mnt", "nfs", opts, NULL)) {
        char * buf;

        checked_asprintf(&buf, "/tmp/mnt/%s", file);

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
