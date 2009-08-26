/*
 * kickstart.h
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

#ifndef H_KICKSTART

#include "loader.h"

#define KS_CMD_NONE	    0
#define KS_CMD_NFS	    1
#define KS_CMD_CDROM	    2
#define KS_CMD_HD	    3
#define KS_CMD_URL	    4
#define KS_CMD_NETWORK      5
#define KS_CMD_TEXT         6
#define KS_CMD_KEYBOARD     7
#define KS_CMD_LANG         8
#define KS_CMD_DD           9
#define KS_CMD_DEVICE      10
#define KS_CMD_CMDLINE     11
#define KS_CMD_GRAPHICAL   12
#define KS_CMD_SELINUX     13
#define KS_CMD_POWEROFF    14
#define KS_CMD_HALT        15
#define KS_CMD_SHUTDOWN    16
#define KS_CMD_MEDIACHECK  17
#define KS_CMD_UPDATES     18

int ksReadCommands(char * cmdFile);
int ksGetCommand(int cmd, char ** last, int * argc, char *** argv);
int ksHasCommand(int cmd);

int isKickstartFileRemote(char *ksFile);
void getKickstartFile(struct loaderData_s * loaderData);
void runKickstart(struct loaderData_s * loaderData);
int getKickstartFromBlockDevice(char *device, char *path);

#endif
