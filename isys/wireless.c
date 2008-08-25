/*
 * wireless.c - wireless card manipulation
 * Some portions from wireless_tools
 *    copyright (c) 1997-2003 Jean Tourrilhes <jt@hpl.hp.com>
 *
 * Copyright (C) 2004  Red Hat, Inc.  All rights reserved.
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
 *
 * Author(s): Jeremy Katz <katzj@redhat.com>
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <sys/socket.h>
#include <sys/types.h>

#include <linux/types.h>
#include <linux/if.h>
#include <linux/wireless.h>

static struct iwreq get_wreq(char * ifname) {
    struct iwreq wreq;

    memset(&wreq, 0, sizeof(wreq));
    strncpy(wreq.ifr_name, ifname, IFNAMSIZ);    
    return wreq;
}

static int get_socket() {
    int sock;

    if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
#ifdef STANDALONE
        fprintf(stderr, "Error creating socket: %s\n", strerror(errno));
#endif
        return -1;
    }

    return sock;
}

int is_wireless_interface(char * ifname) {
    int sock = get_socket();
    struct iwreq wreq = get_wreq(ifname);

    int rc = ioctl(sock, SIOCGIWNAME, &wreq);
    close(sock);

    if (rc < 0) {
        return 0;
    }

    return 1;
}
