/*
 * addrsize.c
 * Generate initrd.addrsize file for s390x platforms.
 * Takes an integer argument and writes out the binary representation of
 * that value to the initrd.addrsize file.
 * https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=197773
 * https://bugzilla.redhat.com/show_bug.cgi?id=546422
 *
 * Copyright (C) 2007-2010  Red Hat, Inc.  All rights reserved.
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
#include <libgen.h>

int main(int argc,char **argv) {
    char *cmd = basename(argv[0]);
    char *address = NULL, *input = NULL, *output = NULL;
    struct stat initrd_stat;
    unsigned int addr = 0, size = 0, zero = 0;
    int fd, rc;
    mode_t mode = S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH;

    if (argc != 4) {
        printf("Generate initrd address and size file used by the .ins LPAR load mechanism\n");
        printf("Usage: %s [address] [initrd] [output file]\n", cmd);
        printf("Example: %s 0x02000000 initrd.img initrd.addrsize\n", cmd);
        return 1;
    }

    address = argv[1];
    input = argv[2];
    output = argv[3];

    rc = stat(input, &initrd_stat);
    if (rc) {
        perror("Error getting initrd stats ");
        return 2;
    }

    addr = htonl(strtoul(address, NULL, 0));
    size = htonl(initrd_stat.st_size);
    fd = open(output, O_CREAT | O_RDWR, mode);

    if (write(fd, &zero, sizeof(int)) == -1) {
        perror("writing initrd.addr (zero) ");
        return 3;
    }

    if (write(fd, &addr, sizeof(int)) == -1) {
        perror("writing initrd.addr (addr) ");
        return 4;
    }

    if (write(fd, &zero, sizeof(int)) == -1) {
        perror("writing initrd.addr (zero) ");
        return 5;
    }

    if (write(fd, &size, sizeof(int)) == -1) {
        perror("writing initrd.addr (size) ");
        return 6;
    }

    close(fd);
    return EXIT_SUCCESS;
}
