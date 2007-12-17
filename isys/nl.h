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

#include <netinet/in.h>
#include <glib.h>

#define BUFSZ 4096

/* Information per interface */
typedef struct _interface_info_t {
   int i;                            /* interface index        */
   char *name;                       /* name (eth0, eth1, ...) */
   struct in_addr ip_addr;           /* IPv4 address (0=none)  */
   struct in6_addr ip6_addr;         /* IPv6 address (0=none)  */
   unsigned char mac[8];             /* MAC address            */
} interface_info_t;

/* Function prototypes */
char *netlink_format_mac_addr(char *buf, unsigned char *mac);
char *netlink_format_ip_addr(int family, interface_info_t *intf, char *buf);
int netlink_create_socket(void);
int netlink_send_dump_request(int sock, int type, int family);
int netlink_get_interface_ip(int index, int family, void *addr);
int netlink_init_interfaces_list(void);
void netlink_interfaces_list_free(void);
char *netlink_interfaces_mac2str(char *ifname);
char *netlink_interfaces_ip2str(char *ifname);

/* Private function prototypes -- used by the functions above */
void _netlink_interfaces_elem_free(gpointer data, gpointer user_data);
gint _netlink_interfaces_elem_find(gconstpointer a, gconstpointer b);
