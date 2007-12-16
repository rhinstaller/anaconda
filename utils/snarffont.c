/*
 * snarffont.c
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

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/kd.h>
#include <stdlib.h>
#include <unistd.h>

void die(char * mess) {
    perror(mess);
    exit(1);
}

#define MAXFONTSIZE	65536

int main(void) {
    unsigned char buf[MAXFONTSIZE];
    struct console_font_op cfo;
    unsigned short map[E_TABSZ];
    struct unipair descs[2048];
    struct unimapdesc d;
    int fd, i;

    if ((fd = open("/dev/tty0", O_RDONLY)) < 0)
	die("open");

    cfo.op = KD_FONT_OP_GET;
    cfo.flags = 0;
    cfo.width = 8;
    cfo.height = 16;
    cfo.charcount = 512;
    cfo.data = buf;
    if (ioctl(fd, KDFONTOP, &cfo))
	die("KDFONTOP KD_FONT_OP_GET"); 

    if (ioctl(fd, GIO_UNISCRNMAP, map))
	die("GIO_UNISCRNMAP");

    d.entry_ct = 2048;
    d.entries = descs;
    if (ioctl(fd, GIO_UNIMAP, &d))
    	die("GIO_UNIMAP");

    i = write(1, &cfo, sizeof(cfo));
    i = write(1, buf, sizeof(buf));
    i = write(1, map, sizeof(map));
    i = write(1, &d.entry_ct, sizeof(d.entry_ct));
    i = write(1, descs, d.entry_ct * sizeof(descs[0]));
    return 0;
}
