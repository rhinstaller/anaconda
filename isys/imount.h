/*
 * imount.h
 *
 * Copyright (C) 2007, 2008, 2009  Red Hat, Inc.  All rights reserved.
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

#ifndef H_IMOUNT
#define H_IMOUNT

#define IMOUNT_ERR_ERRNO          1
#define IMOUNT_ERR_OTHER          2
#define IMOUNT_ERR_MODE           3
#define IMOUNT_ERR_PERMISSIONS    4
#define IMOUNT_ERR_SYSTEM         5
#define IMOUNT_ERR_MOUNTINTERNAL  6
#define IMOUNT_ERR_USERINTERRUPT  7
#define IMOUNT_ERR_MTAB           8
#define IMOUNT_ERR_MOUNTFAILURE   9
#define IMOUNT_ERR_PARTIALSUCC    10

#include <sys/mount.h>		/* for umount() */

#define IMOUNT_RDONLY  1
#define IMOUNT_BIND    2
#define IMOUNT_REMOUNT 4

#define IMOUNT_MODE_MOUNT  1
#define IMOUNT_MODE_UMOUNT 2

int doPwMount(char *dev, char *where, char *fs, char *options, char **err);
int doPwUmount(char *where, char **err);
int mkdirChain(char * origChain);
int mountMightSucceedLater(int mountRc);

#endif
