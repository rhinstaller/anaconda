/*
 * urls.c - url handling code
 *
 * Copyright (C) 1997, 1998, 1999, 2000, 2001, 2002  Red Hat, Inc.
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

#include <arpa/inet.h>
#include <ctype.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <newt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <netdb.h>
#include <errno.h>

#include "ftp.h"
#include "lang.h"
#include "loader.h"
#include "loadermisc.h"
#include "urls.h"
#include "log.h"
#include "windows.h"
#include "net.h"

/* boot flags */
extern uint64_t flags;

/* This is just a wrapper around the windows.c progress callback that accepts
 * the arguments libcurl provides.
 */
int progress_cb(void *data, double dltotal, double dlnow, double ultotal, double ulnow) {
    struct progressCBdata *cb_data = (struct progressCBdata *) data;

    progressCallback(cb_data, dlnow, dltotal);
    return 0;
}

int urlinstTransfer(struct loaderData_s *loaderData, struct iurlinfo *ui,
                    char **extraHeaders, char *dest) {
    struct progressCBdata *cb_data;
    CURLcode status;
    struct curl_slist *headers = NULL;
    char *version;
    FILE *f = NULL;

    logMessage(INFO, "transferring %s", ui->url);

    f = fopen(dest, "w");

    /* Clear out all the old settings, since libcurl preserves them for as
     * long as you use the same handle and settings might have changed.
     */
    curl_easy_reset(loaderData->curl);

    if (asprintf(&version, "anaconda/%s", VERSION) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    curl_easy_setopt(loaderData->curl, CURLOPT_USERAGENT, version);
    curl_easy_setopt(loaderData->curl, CURLOPT_URL, ui->url);
    curl_easy_setopt(loaderData->curl, CURLOPT_WRITEDATA, f);

    /* If a proxy was provided, add the options for that now. */
    if (loaderData->proxy && strcmp(loaderData->proxy, "")) {
        curl_easy_setopt(loaderData->curl, CURLOPT_PROXY, loaderData->proxy);

        if (loaderData->proxyPort && strcmp(loaderData->proxyPort, ""))
            curl_easy_setopt(loaderData->curl, CURLOPT_PROXYPORT,
                             strtol(loaderData->proxyPort, NULL, 10));

        if (loaderData->proxyUser && strcmp(loaderData->proxyUser, ""))
            curl_easy_setopt(loaderData->curl, CURLOPT_PROXYUSERNAME,
                             loaderData->proxyUser);

        if (loaderData->proxyPassword && strcmp(loaderData->proxyPassword, ""))
            curl_easy_setopt(loaderData->curl, CURLOPT_PROXYPASSWORD,
                             loaderData->proxyPassword);
    }

    if (extraHeaders) {
        int i;
        for (i = 0; extraHeaders[i] != NULL; i++) {
            headers = curl_slist_append(headers, extraHeaders[i]);
        }

        curl_easy_setopt(loaderData->curl, CURLOPT_HTTPHEADER, headers);
    }

    /* Only set up the progress bar if we've got a UI to display it. */
    if (FL_CMDLINE(flags)) {
        printf("%s %s...\n", _("Retrieving"), ui->url);
    } else {
        char *filename;

        filename = strrchr(ui->url, '/');
        if (!filename)
           filename = ui->url;

        cb_data = winProgressBar(70, 5, _("Retrieving"), "%s %s...", _("Retrieving"), filename);

        curl_easy_setopt(loaderData->curl, CURLOPT_NOPROGRESS, 0);
        curl_easy_setopt(loaderData->curl, CURLOPT_PROGRESSFUNCTION, progress_cb);
        curl_easy_setopt(loaderData->curl, CURLOPT_PROGRESSDATA, cb_data);
    }

    /* Finally, do the transfer. */
    status = curl_easy_perform(loaderData->curl);
    if (status)
        logMessage(ERROR, "Error downloading %s: %s", ui->url, curl_easy_strerror(status));

    if (!FL_CMDLINE(flags))
       newtPopWindow();

    if (headers)
        curl_slist_free_all(headers);

    fclose(f);
    free(version);

    return status;
}

char * addrToIp(char * hostname) {
    struct in_addr ad;
    struct in6_addr ad6;
    char *ret;
    struct hostent *host;

    if ((ret = malloc(INET6_ADDRSTRLEN+1)) == NULL)
        return hostname;

    if (inet_ntop(AF_INET, &ad, ret, INET_ADDRSTRLEN) != NULL)
        return ret;
    else if (inet_ntop(AF_INET6, &ad6, ret, INET6_ADDRSTRLEN) != NULL)
        return ret;
    else if ((host = gethostbyname(hostname)) != NULL)
        return host->h_name;
    else
        return NULL;
}

int urlMainSetupPanel(struct iurlinfo * ui) {
    newtComponent form, okay, cancel, urlEntry;
    newtComponent answer, text;
    char *url = "";
    char * reflowedText = NULL;
    int width, height;
    newtGrid buttons, grid;
    char * buf = NULL;

    /* Populate the UI with whatever initial value we've got. */
    if (ui && ui->url)
        url = ui->url;

    buttons = newtButtonBar(_("OK"), &okay, _("Back"), &cancel, NULL);

    if (asprintf(&buf,
            _("Please enter the URL containing the %s installation image on your server."),
                 getProductName()) == -1) {
        logMessage(CRITICAL, "%s: %d: %m", __func__, __LINE__);
        abort();
    }

    reflowedText = newtReflowText(buf, 47, 5, 5, &width, &height);
    free(buf);

    text = newtTextbox(-1, -1, width, height, NEWT_TEXTBOX_WRAP);
    newtTextboxSetText(text, reflowedText);
    free(reflowedText);

    urlEntry = newtEntry(22, 8, url, 60, (const char **) &url,
                         NEWT_ENTRY_SCROLL);

    grid = newtCreateGrid(1, 3);
    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT, text,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, urlEntry,
                     0, 0, 0, 1, 0, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 0, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    form = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, form, 1); 
    newtGridWrappedWindow(grid, _("URL Setup"));
    newtGridFree(grid, 1);

    do {
        answer = newtRunForm(form);
        if (answer != cancel) {
            if (!strlen(url)) {
                newtWinMessage(_("Error"), _("OK"),
                               _("You must enter a URL."));
                continue;
            }

            if (!strstr(url, "http://") && !strstr(url, "ftp://")) {
                newtWinMessage(_("Error"), _("OK"),
                               _("URL must be either an ftp or http URL"));
                continue;
            }

            ui->url = strdup(url);

            /* FIXME:  add back in hostname checking */
        }

        break;
    } while (1);

    if (answer == cancel) {
        newtFormDestroy(form);
        newtPopWindow();

        return LOADER_BACK;
    }

    newtFormDestroy(form);
    newtPopWindow();

    return 0;
}
