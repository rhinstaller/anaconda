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
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <glib.h>
#include <nm-client.h>
#include <nm-device.h>
#include <nm-dhcp4-config.h>

#include "copy.h"
#include "dirbrowser.h"
#include "loader.h"
#include "lang.h"
#include "loadermisc.h"
#include "kickstart.h"
#include "method.h"
#include "nfsinstall.h"
#include "net.h"
#include "cdinstall.h"
#include "windows.h"

#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/iface.h"
#include "../pyanaconda/isys/log.h"

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
                         "installation tree and optionally additional "
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

    /* The rest of loader expects opts to be NULL if there are none, but newt
     * gives us "" instead.
     */
    if (newMountOpts && strcmp(newMountOpts, ""))
        *optsptr = newMountOpts;
    else
        *optsptr = NULL;

    return LOADER_OK;
}

/* Parse nfs: url and return its componenets
 *
 * (nfs|nfsiso)[:options]:<server>:<path>
 */
void parseNfsHostPathOpts(char *url, char **host, char **path, char **opts) {
    /* Skip over the leading nfs: or nfsiso: if present. */
    if (!strncmp(url, "nfs:", 4))
        url += 4;
    else if (!strncmp(url, "nfsiso:", 7))
        url += 7;

    logMessage(DEBUGLVL, "parseNfsHostPathOpts url: |%s|", url);

    gchar **parts = g_strsplit(url, ":", 3)     ;
    if (parts == NULL || g_strv_length(parts) < 2) {
        *opts = g_strdup("");
        *host = g_strdup("");
        *path = g_strdup("");
    } else if (g_strv_length(parts) == 2) {
        *opts = g_strdup("");
        *host = g_strdup(parts[0]);
        *path = g_strdup(parts[1]);
        g_strfreev(parts);
    } else {
        *opts = g_strdup(parts[0]);
        *host = g_strdup(parts[1]);
        *path = g_strdup(parts[2]);
        g_strfreev(parts);
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

static int ends_with_iso(char *dirname, struct dirent *ent) {
    char *suffix;

    if (ent->d_type != DT_REG)
        return 0;

    suffix = rindex(ent->d_name, '.');
    return (suffix && !strcmp(suffix, ".iso"));
}

static unsigned int isNfsIso(struct loaderData_s *loaderData) {
    char **files = NULL;
    char *host, *path, *opts, *url;
    char *buf;
    int rc = 0;

    parseNfsHostPathOpts(loaderData->instRepo, &host, &path, &opts);
    checked_asprintf(&url, "%s:%s", host, path);

    if (doPwMount(url, "/mnt/install/isodir", "nfs", opts, NULL)) {
        logMessage(ERROR, "couldn't mount %s to look for NFSISO", url);
        goto cleanup1;
    }

    files = get_file_list("/mnt/install/isodir", ends_with_iso);
    if (!files || !files[0] || !strlen(files[0])) {
        logMessage(ERROR, "no ISO images present in /mnt/install/isodir");
        goto cleanup2;
    }

    /* mount the first image and check for a .treeinfo file */
    checked_asprintf(&buf, "/mnt/install/isodir/%s", files[0]);
    if (doPwMount(buf, "/mnt/install/testmnt", "auto", "ro", NULL)) {
        logMessage(ERROR, "ISO image %s does not contain a .treeinfo file", files[0]);
        goto cleanup3;
    }

    if (access("/mnt/install/testmnt/.treeinfo", R_OK)) {
        logMessage(ERROR, ".treeinfo file is not accessible");
        goto cleanup4;
    }

    free(loaderData->instRepo);
    rc = 1;

    if (opts) {
        checked_asprintf(&loaderData->instRepo, "nfsiso:%s:%s:%s", opts, host, path);
    } else {
        checked_asprintf(&loaderData->instRepo, "nfsiso:%s:%s", host, path);
    }

cleanup4:
    umount("/mnt/install/testmnt");
cleanup3:
    free(buf);
cleanup2:
    umount("/mnt/install/isodir");
cleanup1:
    g_free(host);
    g_free(path);
    g_free(opts);
    free(url);
    return rc;
}

int promptForNfs(struct loaderData_s *loaderData) {
    char *url = NULL;
    char *host = NULL;
    char *directory = NULL;
    char *mountOpts = NULL;

    do {
        if (nfsGetSetup(&host, &directory, &mountOpts) == LOADER_BACK) {
            loaderData->instRepo = NULL;
            return LOADER_BACK;
        }

        if (mountOpts) {
            checked_asprintf(&loaderData->instRepo, "nfs:%s:%s:%s", mountOpts, host,
                             directory);
        } else {
            checked_asprintf(&loaderData->instRepo, "nfs:%s:%s", host, directory);
        }

        checked_asprintf(&url, "%s/.treeinfo", loaderData->instRepo);

        if (getFileFromNfs(url, "/tmp/.treeinfo", loaderData) && !isNfsIso(loaderData)) {
            newtWinMessage(_("Error"), _("OK"),
                           _("The URL provided does not contain an installable tree."));
            free(url);
            continue;
        }

        free(url);
        break;
    } while (1);

    loaderData->method = METHOD_NFS;
    return LOADER_OK;
}

int loadNfsImages(struct loaderData_s *loaderData) {
    char *host, *path, *opts;
    char *url;

    logMessage(DEBUGLVL, "looking for extras for NFS install");

    if (!loaderData->instRepo)
        return 0;

    parseNfsHostPathOpts(loaderData->instRepo, &host, &path, &opts);

    checked_asprintf(&url, "%s:%s/RHupdates", host, path);
    logMessage(INFO, "Looking for updates in %s", url);

    if (!doPwMount(url, "/mnt/install/update-disk", "nfs", opts, NULL)) {
        logMessage(INFO, "Using RHupdates/ for NFS install");
        copyDirectory("/mnt/install/update-disk", "/tmp/updates", NULL, NULL);
        umount("/mnt/install/update-disk");
        unlink("/mnt/install/update-disk");
    } else {
        logMessage(INFO, "No RHupdates/ directory found, skipping");
    }

    free(url);
    checked_asprintf(&url, "%s:%s", host, path);

    if (!doPwMount(url, "/mnt/install/disk-image", "nfs", opts, NULL)) {
        free(url);

        logMessage(INFO, "Looking for updates in %s/updates.img", loaderData->instRepo);
        copyUpdatesImg("/mnt/install/disk-image/updates.img");

        logMessage(INFO, "Looking for product in %s/product.img", loaderData->instRepo);
        copyProductImg("/mnt/install/disk-image/product.img");

        umount("/mnt/install/disk-image");
        unlink("/mnt/install/disk-image");
    } else {
        logMessage(INFO, "Couldn't mount %s for updates and product", loaderData->instRepo);
        free(url);
    }

    g_free(host);
    g_free(path);
    g_free(opts);
    return 1;
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
        if (! is_connected_state(state)) {
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
            if (isValidIPv4Address(server_name)) {
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

    if (!doPwMount(host, "/mnt/install/testmnt", "nfs", opts, NULL)) {
        char * buf;

        checked_asprintf(&buf, "/mnt/install/testmnt/%s", file);

        if (copyFile(buf, dest)) {
            logMessage(ERROR, "failed to copy file to %s", dest);
            failed = 1;
        }

        free(buf);
    } else {
        logMessage(ERROR, "failed to mount nfs source");
        failed = 1;
    }

    g_free(host);
    g_free(path);
    g_free(opts);
    if (ip) free(ip);

    if (umount("/mnt/install/testmnt") == -1)
        logMessage(ERROR, "could not unmount /mnt/install/testmnt in getFileFromNfs: %s", strerror(errno));
    else
        unlink("/mnt/install/testmnt");

    return failed;
}

int kickstartFromNfs(char * url, struct loaderData_s * loaderData) {
    return getFileFromNfs(url, "/tmp/ks.cfg", loaderData);
}

/* vim:set shiftwidth=4 softtabstop=4: */
