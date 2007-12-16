/*
 * geninitrdsz.c
 * Generate initrd.size file for zSeries platforms.
 * Takes an integer argument and writes out the binary representation of
 * that value to the initrd.size file.
 * https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=197773
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

#include <stdio.h>
#include <stdlib.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

int main(int argc,char **argv) {
    unsigned int zero = 0;
    int fd;
    unsigned int size;
    mode_t mode = S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH;

    if (argc != 3) {
        printf("Usage: %s [integer size] [output file]\n", basename(argv[0]));
        printf("Example: %s 12288475 initrd.size\n", basename(argv[0]));
        return 0;
    }

    size = htonl(atoi(argv[1]));
    fd = open(argv[2], O_CREAT | O_RDWR, mode);

    if (write(fd, &zero, sizeof(int)) == -1) {
        perror("writing initrd.size (zero)");
        return errno;
    }

    if (write(fd, &size, sizeof(int)) == -1) {
        perror("writing initrd.size (size)");
        return errno;
    }

    close(fd);
    return 0;
}
