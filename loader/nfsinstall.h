/*
 * nfsinstall.h
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

#ifndef NFSINSTALL_H
#define NFSINSTALL_H

#include "method.h"

struct nfsInstallData {
    char * host;
    char * directory;
    char * mountOpts;
};


void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv);
int kickstartFromNfs(char * url, struct loaderData_s * loaderData);
char * mountNfsImage(struct installMethod * method,
                     char * location, struct loaderData_s * loaderData);
int getFileFromNfs(char * url, char * dest, struct loaderData_s * loaderData);
void parseNfsHostPathOpts(char * url, char ** host, char ** path, char ** opts);

#endif
