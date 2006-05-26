/*
 * nl.h - Netlink helper functions, the header file
 *
 * Copyright 2006 Red Hat, Inc.
 *
 * David Cantrell <dcantrell@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <netinet/in.h>
#include <glib.h>

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
