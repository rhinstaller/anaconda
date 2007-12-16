/*
 * readmap.c
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
#include <sys/ioctl.h>
#include <linux/keyboard.h>
#ifdef NR_KEYS
#undef NR_KEYS
#define NR_KEYS 128
#endif

#include <linux/kd.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#include "../isys/lang.h"

int main(int argc, char ** argv) {
    int console;
    int kmap, key;
    struct kbentry entry;
    int keymaps[MAX_NR_KEYMAPS];
    int count = 0;
    int out;
    short keymap[NR_KEYS];
    int magic = KMAP_MAGIC;
    int verbose = 0;

    if (argc != 2) {
	printf("bad usage\n");
	exit(1);
    }

    if (getenv("DEBUG") != NULL)
        verbose = 1;
 
    memset(keymaps, 0, sizeof(keymaps));

    console = open("/dev/tty0", O_RDWR);
    if (console < 0) {
	perror("open VGA+KBD");
	exit(1);
    }

    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	for (key = 0; key < NR_KEYS; key++) {
	    entry.kb_index = key;
	    entry.kb_table = kmap;
	    if (ioctl(console, KDGKBENT, &entry)) {
		perror("ioctl failed");
		exit(1);
	    } else if (KTYP(entry.kb_value) != KT_SPEC) {
		keymaps[kmap] = 1;
		count++;
		break;
	    }
	}
    }

    if (verbose) fprintf(stderr, "found %d valid keymaps\n", count);

    if (verbose) fprintf(stderr, "creating keymap file %s\n", argv[1]);
    if ((out = open(argv[1], O_WRONLY | O_CREAT | O_TRUNC, 0666)) < 1) {
	perror("open keymap");
	exit(1);
    }

    if (write(out, &magic, sizeof(magic)) != sizeof(magic)) {
	perror("write magic");
	exit(1);
    }

    if (write(out, keymaps, sizeof(keymaps)) != sizeof(keymaps)) {
	perror("write header");
	exit(1);
    }
        
    for (kmap = 0; kmap < MAX_NR_KEYMAPS; kmap++) {
	if (!keymaps[kmap]) continue;
	for (key = 0; key < NR_KEYS; key++) {
	    entry.kb_index = key;
	    entry.kb_table = kmap;
	    if (ioctl(console, KDGKBENT, &entry)) {
		perror("ioctl failed");
		exit(1);
	    } else {
		keymap[key] = entry.kb_value;
	    }
	}

	if (write(out, keymap, sizeof(keymap)) != sizeof(keymap)) {
	    perror("write keymap");
	    exit(1);
	}
    }

    close(out);

    return 0;
}
