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

#include "loader.h"
#include "windows.h"

struct iurlinfo {
    char * url;
};

int splitProxyParam(char *param, char **user, char **password, char **proxy);
int urlMainSetupPanel(struct loaderData_s *loaderData, struct iurlinfo * ui);
int urlinstTransfer(struct loaderData_s *loaderData, struct iurlinfo *ui,
                    char **extraHeaders, char *dest);

#endif
