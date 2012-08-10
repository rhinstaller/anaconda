/*
 * lang.c
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

#include <alloca.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <linux/keyboard.h>
#ifdef NR_KEYS
#undef NR_KEYS
#define NR_KEYS 128
#endif

#include <zlib.h>

#include "linux/kd.h"

#include "isys.h"
#include "lang.h"

int isysSetUnicodeKeymap(void) {
    int console;

#if defined (__s390__) || defined (__s390x__)
    return 0;
#endif
    console = open("/dev/console", O_RDWR);
    if (console < 0)
	return -EACCES;

    /* place keyboard in unicode mode */
    ioctl(console, KDSKBMODE, K_UNICODE);
    close(console);
    return 0;
}

