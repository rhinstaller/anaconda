/*
 * isofs.c
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

#include <fcntl.h>
#include <string.h>
#include <unistd.h>

#define BLOCK_SIZE 2048
 
/* returns 1 if file is an ISO, 0 otherwise */
int fileIsIso(const char * file) {
    int blkNum;
    char magic[5];
    int fd;

    fd = open(file, O_RDONLY);
    if (fd < 0)
	return 0;

    for (blkNum = 16; blkNum < 100; blkNum++) {
	if (lseek(fd, blkNum * BLOCK_SIZE + 1, SEEK_SET) < 0) {
	    close(fd);
	    return 0;
	}

	if (read(fd, magic, sizeof(magic)) != sizeof(magic)) {
	    close(fd);
	    return 0;
	}

	if (!strncmp(magic, "CD001", 5)) {
	    close(fd);
	    return 1;
	}
    }

    close(fd); 
    return 0;
}
