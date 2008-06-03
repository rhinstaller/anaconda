/*
 * urls.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#ifndef H_LOADER_URLS
#define H_LOADER_URLS

enum urlprotocol_t { URL_METHOD_FTP, URL_METHOD_HTTP };
typedef enum urlprotocol_t urlprotocol;

struct iurlinfo {
    urlprotocol protocol;
    char * address;
    char * login;
    char * password;
    char * prefix;
    char * proxy;
    char * proxyPort;
    int ftpPort;
};

int convertURLToUI(char *url, struct iurlinfo *ui);
char *convertUIToURL(struct iurlinfo *ui);

int setupRemote(struct iurlinfo * ui);
int urlMainSetupPanel(struct iurlinfo * ui);
int urlSecondarySetupPanel(struct iurlinfo * ui);
int urlinstStartTransfer(struct iurlinfo * ui, char *path, char *extraHeaders);
int urlinstFinishTransfer(struct iurlinfo * ui, int fd);

#endif
