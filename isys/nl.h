/*
 * nl.h - Netlink helper functions, the header file
 *
 * Copyright (C) 2006  Red Hat, Inc.  All rights reserved.
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
 * Author(s): David Cantrell <dcantrell@redhat.com>
 */

#include <netlink/cache.h>

/* Function prototypes */
struct nl_cache *nl_get_link_cache(struct nl_handle **handle);
char *nl_mac2str(char *ifname);
char *nl_ip2str(char *ifname);
int nl_set_device_mtu(char *ifname, int mtu);
