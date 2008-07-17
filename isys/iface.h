/*
 * iface.h
 *
 * Copyright (C) 2006, 2007, 2008  Red Hat, Inc.  All rights reserved.
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
#include <netlink/socket.h>

/* Function prototypes */
struct nl_cache *iface_get_link_cache(struct nl_handle **handle);
char *iface_mac2str(char *ifname);
char *iface_ip2str(char *ifname);
int iface_set_interface_mtu(char *ifname, int mtu);
