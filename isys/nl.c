/*
 * nl.c - Netlink helper functions
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

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>

#include <sys/socket.h>
#include <sys/types.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <arpa/inet.h>
#include <net/if_arp.h>

#include <glib.h>

#include "nl.h"

/* A linked list of interface_info_t structures (see nl.h) */
static GSList *interfaces = NULL;

/**
 * Not really Netlink-specific, but handy nonetheless.  Takes a MAC address
 * and converts it to the familiar hexidecimal notation for easy reading.
 *
 * @param mac The unsigned char MAC address value.
 * @param buf The string to write the formatted address to.
 * @return Pointer to buf.
 */
char *netlink_format_mac_addr(char *buf, unsigned char *mac) {
   sprintf(buf, "%02x:%02x:%02x:%02x:%02x:%02x",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
   return buf;
}

/**
 * Return a human-readable IP address (either v4 or v6).
 *
 * @param family The address family.
 * @param intf The interface_info_t structure with the IP address info.
 * @param buf The buffer to write the formatted IP address to.
 * @return A pointer to buf.
 */
char *netlink_format_ip_addr(int family, interface_info_t *intf, char *buf) {
   char ipbuf[256];

   memset(ipbuf, 0, sizeof(ipbuf));
   switch (family) {
      case AF_INET:
         inet_ntop(family, &(intf->ip_addr), ipbuf, sizeof(ipbuf));
         break;
      case AF_INET6:
         inet_ntop(family, &(intf->ip6_addr), ipbuf, sizeof(ipbuf));
         break;
   }

   memcpy(buf, ipbuf, sizeof(ipbuf));
   return buf;
}

/**
 * Create a new PF_NETLINK socket for communication with the kernel Netlink
 * layer.  Open with NETLINK_ROUTE protocol since we want IPv4 and IPv6
 * interface, address, and routing information.
 *
 * @return Handle to new socket or -1 on error.
 */
int netlink_create_socket(void) {
   int sock;

   sock = socket(PF_NETLINK, SOCK_RAW, NETLINK_ROUTE);
   if (sock < 0) {
      perror("netlink socket");
      return -1;
   }

   return sock;
}

/**
 * Send a dump request message for the specified information in the
 * specified family type.  Family may be AF_INET or AF_INET6, for
 * example.  The request type should be a GET type as specified in
 * /usr/include/linux/rtnetlink.h (for example, RTM_GETLINK).
 *
 * @param sock The Netlink socket to use.
 * @param type The Netlink request type.
 * @param family The address family.
 * @return The number of characters sent or -1 on error.
 */
int netlink_send_dump_request(int sock, int type, int family) {
   int ret;
   char buf[4096];
   struct sockaddr_nl snl;
   struct nlmsghdr *nlh;
   struct rtgenmsg *g;

   memset(&snl, 0, sizeof(snl));
   snl.nl_family = AF_NETLINK;

   memset(buf, 0, sizeof(buf));
   nlh = (struct nlmsghdr *)buf;
   g = (struct rtgenmsg *)(buf + sizeof(struct nlmsghdr));

   nlh->nlmsg_len = NLMSG_LENGTH(sizeof(struct rtgenmsg));
   nlh->nlmsg_flags = NLM_F_REQUEST|NLM_F_DUMP;
   nlh->nlmsg_type = type;
   g->rtgen_family = family;

   ret = sendto(sock, buf, nlh->nlmsg_len, 0, (struct sockaddr *)&snl,
                sizeof(snl));
   if (ret < 0) {
      perror("netlink_send_dump_request sendto");
      return -1;
   }

   return ret;
}

/**
 * Look for an IP address for the given interface.
 *
 * @param index The interface index number.
 * @param family The address family (AF_INET or AF_INET6).
 * @param addr Pointer to where we should write the IP address.
 * @return -1 on error, 0 on success.
 */
int netlink_get_interface_ip(int index, int family, void *addr) {
   int sock, ret, len, alen;
   char buf[4096];
   struct nlmsghdr *nlh;
   struct ifaddrmsg *ifa;
   struct rtattr *rta;
   struct rtattr *tb[IFLA_MAX+1];

   /* get a socket */
   if ((sock = netlink_create_socket()) == -1) {
      perror("netlink_create_socket in netlink_get_interface_ip");
      close(sock);
      return -1;
   }

   /* send dump request */
   if (netlink_send_dump_request(sock, RTM_GETADDR, family) == -1) {
      perror("netlink_send_dump_request in netlink_get_interface_ip");
      close(sock);
      return -1;
   }

   /* read back messages */
   memset(buf, 0, sizeof(buf));
   ret = recvfrom(sock, buf, sizeof(buf), 0, NULL, 0);
   if (ret < 0) {
      perror("recvfrom in netlink_init_interfaces_table");
      close(sock);
      return -1;
   }

   nlh = (struct nlmsghdr *) buf;
   while (NLMSG_OK(nlh, ret)) {
      switch (nlh->nlmsg_type) {
         case NLMSG_DONE:
            break;
         case RTM_NEWADDR:
            break;
         default:
            nlh = NLMSG_NEXT(nlh, ret);
            continue;
      }

      /* RTM_NEWADDR */
      ifa = NLMSG_DATA(nlh);
      rta = IFA_RTA(ifa);
      len = NLMSG_PAYLOAD(nlh, 0);     /* IFA_PAYLOAD(nlh) ???? */

      if (ifa->ifa_family != family) {
         nlh = NLMSG_NEXT(nlh, ret);
         continue;
      }

      while (RTA_OK(rta, len)) {
         if (rta->rta_type <= len)
            tb[rta->rta_type] = rta;
         rta = RTA_NEXT(rta, len);
      }

      alen = RTA_PAYLOAD(tb[IFA_ADDRESS]);

      /* write the address */
      if (tb[IFA_ADDRESS] && ifa->ifa_index == index) {
         memset(addr, 0, sizeof(*addr));
         switch (family) {
            case AF_INET:
               memcpy(addr, (struct in_addr *)RTA_DATA(tb[IFA_ADDRESS]), alen);
               break;
            case AF_INET6:
               memcpy(addr, (struct in6_addr *)RTA_DATA(tb[IFA_ADDRESS]), alen);
               break;
         }

         close(sock);
         return 0;
      }

      /* next netlink msg */
      nlh = NLMSG_NEXT(nlh, ret);
   }

   close(sock);
   return 0;
}

/**
 * Initialize the interfaces linked list with the interface name, MAC
 * address, and IP addresses.  This function is only called once to
 * initialize the structure, but may be called again if the structure
 * should be reinitialized.
 *
 * @return 0 on succes, -1 on error.
 */
int netlink_init_interfaces_list(void) {
   int sock, ret, len, alen, r;
   char buf[4096];
   struct nlmsghdr *nlh;
   struct ifinfomsg *ifi;
   struct rtattr *rta;
   struct rtattr *tb[IFLA_MAX+1];
   interface_info_t *intfinfo;

   /* get a socket */
   if ((sock = netlink_create_socket()) == -1) {
      perror("netlink_create_socket in netlink_init_interfaces_table");
      close(sock);
      return -1;
   }

   /* send dump request */
   if (netlink_send_dump_request(sock, RTM_GETLINK, AF_NETLINK) == -1) {
      perror("netlink_send_dump_request in netlink_init_interfaces_table");
      close(sock);
      return -1;
   }

   /* read back messages */
   memset(buf, 0, sizeof(buf));
   ret = recvfrom(sock, buf, sizeof(buf), 0, NULL, 0);
   if (ret < 0) {
      perror("recvfrom in netlink_init_interfaces_table");
      close(sock);
      return -1;
   }

   nlh = (struct nlmsghdr *) buf;
   while (NLMSG_OK(nlh, ret)) {
      switch (nlh->nlmsg_type) {
         case NLMSG_DONE:
            break;
         case RTM_NEWLINK:
            break;
         default:
            nlh = NLMSG_NEXT(nlh, ret);
            continue;
      }

      /* RTM_NEWLINK */
      memset(tb, 0, sizeof(tb));
      memset(tb, 0, sizeof(struct rtattr *) * (IFLA_MAX + 1));

      ifi = NLMSG_DATA(nlh);
      rta = IFLA_RTA(ifi);
      len = IFLA_PAYLOAD(nlh);

      /* void and none are bad */
      if (ifi->ifi_type == ARPHRD_VOID || ifi->ifi_type == ARPHRD_NONE) {
         nlh = NLMSG_NEXT(nlh, ret);
         continue;
      }

      while (RTA_OK(rta, len)) {
         if (rta->rta_type <= len)
            tb[rta->rta_type] = rta;
         rta = RTA_NEXT(rta, len);
      }

      alen = RTA_PAYLOAD(tb[IFLA_ADDRESS]);

      /* we have an ethernet MAC addr if alen=6 */
      if (alen == 6) {
         /* make some room! */
         intfinfo = malloc(sizeof(struct _interface_info_t));
         if (intfinfo == NULL) {
            perror("malloc in netlink_init_interfaces_table");
            close(sock);
            return -1;
         }

         /* copy the interface index */
         intfinfo->i = ifi->ifi_index;

         /* copy the interface name (eth0, eth1, ...) */
         intfinfo->name = strndup((char *) RTA_DATA(tb[IFLA_IFNAME]),
                                  sizeof(RTA_DATA(tb[IFLA_IFNAME])));

         /* copy the MAC addr */
         memcpy(&intfinfo->mac, RTA_DATA(tb[IFLA_ADDRESS]), alen);

         /* get the IPv4 address of this interface (if any) */
         r = netlink_get_interface_ip(intfinfo->i, AF_INET, &intfinfo->ip_addr);
         if (r == -1)
            intfinfo->ip_addr.s_addr = 0;

         /* get the IPv6 address of this interface (if any) */
         r = netlink_get_interface_ip(intfinfo->i,AF_INET6,&intfinfo->ip6_addr);
/* XXX: why this no work?
         if (r == -1)
            intfinfo->ip6_addr.s6_addr = 0;
*/

         /* add this interface */
         interfaces = g_slist_append(interfaces, intfinfo);
      }

      /* next netlink msg */
      nlh = NLMSG_NEXT(nlh, ret);
   }

   close(sock);
   return 0;
}

#ifdef TESTING
void print_interfaces(gpointer data, gpointer user_data) {
   char buf[20];
   char ipbuf[256];
   interface_info_t *intf;

   intf = (interface_info_t *) data;
   printf("Interface %d\n", intf->i);
   printf("   Name: %s\n", intf->name);
   printf("   IPv4: %s\n", netlink_format_ip_addr(AF_INET, intf, ipbuf));
   printf("   IPv6: %s\n", netlink_format_ip_addr(AF_INET6, intf, ipbuf));
   printf("    MAC: %s\n\n", netlink_format_mac_addr(buf, intf->mac));

   return;
}

int main(void) {
   if (netlink_init_interfaces_list() == -1) {
      fprintf(stderr, "netlink_init_interfaces_list failure: %s\n", __func__);
      fflush(stderr);
      return EXIT_FAILURE;
   }

   g_slist_foreach(interfaces, print_interfaces, NULL);

   return EXIT_SUCCESS;
}
#endif
