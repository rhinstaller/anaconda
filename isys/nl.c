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
#include <linux/if.h>
#include <arpa/inet.h>
#include <net/if_arp.h>

#include <glib.h>

#include "nl.h"
#include "str.h"

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
    if (buf == NULL) {
        if ((buf = malloc(20)) == NULL) {
            perror("malloc in netlink_format_mac_addr");
            return NULL;
        }
    }

    sprintf(buf, "%02x:%02x:%02x:%02x:%02x:%02x",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    return str2upper(buf);
}

/**
 * Convert cylon-readable IP address to human-readable format (either v4
 * or v6).
 *
 * @param family The address family.
 * @param intf The interface_info_t structure with the IP address info.
 * @param buf The buffer to write the formatted IP address to.
 * @return A pointer to buf.
 */
char *netlink_format_ip_addr(int family, interface_info_t *intf, char *buf) {
    int iplen;

    if (family == AF_INET6)
        iplen = INET6_ADDRSTRLEN;
    else
        iplen = INET_ADDRSTRLEN;

    if (buf == NULL) {
        if ((buf = malloc(iplen)) == NULL) {
            perror("malloc in netlink_format_ip_addr");
            return NULL;
        }

        memset(buf, 0, iplen);
    }

    switch (family) {
        case AF_INET:
            inet_ntop(family, &(intf->ip_addr), buf, iplen);
            break;
        case AF_INET6:
            inet_ntop(family, &(intf->ip6_addr), buf, iplen);
            break;
    }

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
    char buf[BUFSZ];
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
    ssize_t bufsz, readsz;
    char *buf = NULL;
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
    ret = netlink_send_dump_request(sock, RTM_GETADDR, family);
    if (ret <= 0) {
        if (ret < 0)
            perror("netlink_send_dump_request in netlink_get_interface_ip");
        close(sock);
        return ret < 0 ? -1 : 0;
    }

    /* MSG_TRUNC doesn't actually seem to /work/ with netlink on RHEL 5,
     * so we do this lame growth game until we have a buffer big enough.
     * When we're done (which is the first time if MSG_TRUNC does its job),
     * bufsz is the size of the message. Then we allocate a real buffer and
     * do recvfrom again without MSG_PEEK. */
    len = 32;
    do {
        len <<= 1;
        char tmpbuf[len];
        bufsz = recvfrom(sock, tmpbuf, len, MSG_PEEK|MSG_TRUNC|MSG_WAITALL,
            NULL, 0);
        if (bufsz < 0 && errno == EAGAIN)
                bufsz = len;
    } while (bufsz == len);

    if (bufsz <= 0) {
        if (bufsz < 0)
            perror("1st recvfrom in netlink_get_interface_ip");
        close(sock);
        return -1;
    }

    if ((buf = alloca(bufsz)) == NULL) {
        perror("alloca on msg buf in netlink_get_interface_ip");
        close(sock);
        return -1;
    }
    memset(buf, '\0', bufsz);

    while ((readsz = recvfrom(sock, buf, bufsz, MSG_WAITALL, NULL, 0)) <= 0) {
        if (readsz < 0) {
            if (errno == EAGAIN)
                continue;
            perror("2nd recvfrom in netlink_get_interface_ip");
        }
        close(sock);
        return -1;
    }

    nlh = (struct nlmsghdr *) buf;
    while (NLMSG_OK(nlh, readsz)) {
        switch (nlh->nlmsg_type) {
            case NLMSG_DONE:
                break;
            case RTM_NEWADDR:
                break;
            default:
                nlh = NLMSG_NEXT(nlh, readsz);
                continue;
        }

        /* RTM_NEWADDR */
        ifa = NLMSG_DATA(nlh);
        rta = IFA_RTA(ifa);
        len = IFA_PAYLOAD(nlh);

        if (ifa->ifa_family != family) {
            nlh = NLMSG_NEXT(nlh, readsz);
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
            switch (family) {
                case AF_INET:
                    memset(addr, 0, sizeof(struct in_addr));
                    memcpy(addr, (struct in_addr *)RTA_DATA(tb[IFA_ADDRESS]), alen);
                    break;
                case AF_INET6:
                    memset(addr, 0, sizeof(struct in6_addr));
                    memcpy(addr, (struct in6_addr *)RTA_DATA(tb[IFA_ADDRESS]), alen);
                    break;
            }

            close(sock);
            return 0;
        }

        /* next netlink msg */
        nlh = NLMSG_NEXT(nlh, readsz);
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
    int sock, len, alen, r, namelen;
    ssize_t bufsz, readsz;
    char *buf = NULL;
    struct nlmsghdr *nlh;
    struct ifinfomsg *ifi;
    struct rtattr *rta;
    struct rtattr *tb[IFLA_MAX+1];
    interface_info_t *intfinfo;

    /* if interfaces has stuff, free it now and read again */
    if (interfaces != NULL)
        netlink_interfaces_list_free();

    /* get a socket */
    if ((sock = netlink_create_socket()) == -1) {
        perror("netlink_create_socket in netlink_init_interfaces_list");
        close(sock);
        return -1;
    }

    /* send dump request */
    r = netlink_send_dump_request(sock, RTM_GETLINK, AF_NETLINK);
    if (r <= 0) {
        if (r < 0)
            perror("netlink_send_dump_request in netlink_init_interfaces_list");
        close(sock);
        return r < 0 ? -1 : r;
    }

    /* MSG_TRUNC doesn't actually seem to /work/ with netlink on RHEL 5,
     * so we do this lame growth game until we have a buffer big enough.
     * When we're done (which is the first time if MSG_TRUNC does its job),
     * bufsz is the size of the message. Then we allocate a real buffer and
     * do recvfrom again without MSG_PEEK. */
    len = 32;
    do {
        len <<= 1;
        char tmpbuf[len];
        bufsz = recvfrom(sock, tmpbuf, len, MSG_PEEK|MSG_TRUNC|MSG_WAITALL,
            NULL, 0);
        if (bufsz < 0 && errno == EAGAIN)
                bufsz = len;
    } while (bufsz == len);

    if (bufsz <= 0) {
        if (bufsz < 0)
            perror("1st recvfrom in netlink_get_interface_list");
        close(sock);
        return -1;
    }

    if ((buf = alloca(bufsz)) == NULL) {
        perror("alloca on msg buf in netlink_get_interface_list");
        close(sock);
        return -1;
    }
    memset(buf, '\0', bufsz);

    while ((readsz = recvfrom(sock, buf, bufsz, MSG_WAITALL, NULL, 0)) <= 0) {
        if (readsz < 0) {
            if (errno == EAGAIN)
                continue;
            perror("2nd recvfrom in netlink_get_interface_list");
        }
        close(sock);
        return -1;
    }

    nlh = (struct nlmsghdr *) buf;
    while (NLMSG_OK(nlh, readsz)) {
        switch (nlh->nlmsg_type) {
            case NLMSG_DONE:
                break;
            case RTM_NEWLINK:
                break;
            default:
                nlh = NLMSG_NEXT(nlh, readsz);
                continue;
        }

        /* RTM_NEWLINK */
        memset(tb, 0, sizeof(tb));
        memset(tb, 0, sizeof(struct rtattr *) * (IFLA_MAX + 1));

        ifi = NLMSG_DATA(nlh);
        rta = IFLA_RTA(ifi);
        len = IFLA_PAYLOAD(nlh);

        /* we only do things with ethernet mac addrs, so ... */
        if (ifi->ifi_type != ARPHRD_ETHER) {
            nlh = NLMSG_NEXT(nlh, readsz);
            continue;
        }

        namelen = 0;

        while (RTA_OK(rta, len)) {
            if (rta->rta_type <= len) {
                if (rta->rta_type == IFLA_IFNAME) {
                    namelen = rta->rta_len;
                }

                tb[rta->rta_type] = rta;
            }

            rta = RTA_NEXT(rta, len);
        }

        if (tb[IFLA_ADDRESS] != NULL)
            alen = RTA_PAYLOAD(tb[IFLA_ADDRESS]);
        else
            alen = 0;

        /* we have an ethernet MAC addr if alen=6 */
        if (alen == 6) {
            /* make some room! */
            intfinfo = malloc(sizeof(struct _interface_info_t));
            if (intfinfo == NULL) {
                perror("malloc in netlink_init_interfaces_list");
                close(sock);
                return -1;
            }

            /* copy the interface index */
            intfinfo->i = ifi->ifi_index;

            /* copy the interface name (eth0, eth1, ...) */
            if (namelen > 0) {
                intfinfo->name = strndup((char *) RTA_DATA(tb[IFLA_IFNAME]),
                                         namelen);
            } else {
                intfinfo->name = NULL;
            }

            /* copy the MAC addr */
            memcpy(&intfinfo->mac, RTA_DATA(tb[IFLA_ADDRESS]), alen);

            if (ifi->ifi_flags & IFF_RUNNING) {
                /* get the IPv4 address of this interface (if any) */
                r = netlink_get_interface_ip(intfinfo->i, AF_INET, &intfinfo->ip_addr);
                if (r < 0)
                    memset(&intfinfo->ip_addr, 0, sizeof(struct in_addr));

                /* get the IPv6 address of this interface (if any) */
                r = netlink_get_interface_ip(intfinfo->i, AF_INET6, &intfinfo->ip6_addr);
                if (r < 0)
                    memset(&intfinfo->ip6_addr, 0, sizeof(struct in6_addr));
            } else {
                memset(&intfinfo->ip_addr, 0, sizeof(struct in_addr));
                memset(&intfinfo->ip6_addr, 0, sizeof(struct in6_addr));
            }

            /* add this interface */
            interfaces = g_slist_append(interfaces, intfinfo);
        }

        /* next netlink msg */
        nlh = NLMSG_NEXT(nlh, readsz);
    }

    close(sock);
    return 0;
}

/**
 * Take the cylon-readable IP address for the specified device and format
 * it for human reading.  NOTE:  This function will check for IPv6 and IPv4
 * addresses.  In the case where the interface has both, the IPv4 address
 * is returned.  The only way you will get an IPv6 address from this function
 * is if that's the only address configured for the interface.
 *
 * @param ifname The interface name (e.g., eth0).
 * @return The human-readable IP address (either IPv4 or IPv6) or NULL on
 *         error/no match.
 */
char *netlink_interfaces_ip2str(char *ifname) {
    char *ret = NULL;
    GSList *e;
    interface_info_t *intf;

    if (ifname == NULL)
        return NULL;

    /* init the interfaces list if it's empty or if nothing is found */
    e = g_slist_find_custom(interfaces,ifname,&_netlink_interfaces_elem_find);
    if (interfaces == NULL || e == NULL) {
        int r = netlink_init_interfaces_list();
        if (r <= 0) {
            if (r < 0)
                perror("netlink_init_interfaces_list in netlink_interface_ip2str");
            return NULL;
        }
    }

    /* search */
    e = g_slist_find_custom(interfaces,ifname,&_netlink_interfaces_elem_find);
    if (e == NULL) {
        return NULL;
    } else {
        intf = (interface_info_t *) e->data;

        if (intf->ip_addr.s_addr == 0 && intf->ip6_addr.s6_addr[0] == 0)
            /* neither IP set, return null */
            ret = NULL;
        else if (intf->ip_addr.s_addr == 0 && intf->ip6_addr.s6_addr[0] != 0)
            /* only IPv6 addr, return that */
            ret = netlink_format_ip_addr(AF_INET6, intf, ret);
        else if (intf->ip_addr.s_addr != 0)
            /* if IPv4 is set, return that (regardless of IPv6 value) */
            ret = netlink_format_ip_addr(AF_INET, intf, ret);
        else
            /* we have no idea what happened, return NULL */
            ret = NULL;

        return ret;
    }
}

/**
 * Take the cylon-readable MAC address for the specified device and
 * format it for human reading.
 *
 * @param ifname The interface name (e.g., eth0).
 * @return The human-readable MAC address (e.g., 01:0A:3E:4B:91:12) or NULL
 *            on error.
 */
char *netlink_interfaces_mac2str(char *ifname) {
    char *ret = NULL;
    GSList *e;
    interface_info_t *intf;
    int r;

    if (ifname == NULL)
        return NULL;

    /* init the interfaces list if it's empty */
    if (interfaces == NULL) {
        r = netlink_init_interfaces_list();
        if (r <= 0) {
            if (r < 0)
                perror("netlink_init_interfaces_list in netlink_interface_mac2str");
            return NULL;
        }
    }

    e = g_slist_find_custom(interfaces,ifname,&_netlink_interfaces_elem_find);
    if (e == NULL) {
        return NULL;
    } else {
        intf = (interface_info_t *) e->data;
        ret = netlink_format_mac_addr(ret, intf->mac);
        return ret;
    }
}

/**
 * Free memory for each element of the specified linked list.  Frees the
 * list after all elements have been freed (say 'free' some more).
 */
void netlink_interfaces_list_free(void) {
    g_slist_foreach(interfaces, &_netlink_interfaces_elem_free, NULL);
    g_slist_free(interfaces);
    interfaces = NULL;
    return;
}

/**
 * Callback function for netlink_interfaces_list_free.  Frees an individual
 * list element.
 *
 * @see netlink_interfaces_list_free
 */
void _netlink_interfaces_elem_free(gpointer data, gpointer user_data) {
    free(data);
    data = NULL;
    return;
}

/**
 * Compares one list element to the specified interface name.  Callback
 * function used to locate a list element by interface name.
 *
 * @see netlink_interfaces_mac2str
 * @see netlink_interfaces_ip2str
 */
gint _netlink_interfaces_elem_find(gconstpointer a, gconstpointer b) {
    char *ifname = (char *) b;
    GSList *elemdata = (GSList *) a;
    interface_info_t *intf;

    intf = (interface_info_t *) elemdata;
    if (intf->name == NULL)
        return -1;
    else
        return strncmp(ifname, intf->name, strlen(ifname));
}

#ifdef TESTING
void print_interfaces(gpointer data, gpointer user_data) {
    char *buf = NULL;
    char *ipbuf = NULL;
    interface_info_t *intf;

    intf = (interface_info_t *) data;
    printf("Interface %d\n", intf->i);
    printf("    Name: %s\n", intf->name);
    if (intf->ip_addr.s_addr != 0)
        printf("    IPv4: %s\n", netlink_format_ip_addr(AF_INET, intf, ipbuf));
    else
        printf("    IPv4: not set\n");
    if (intf->ip6_addr.s6_addr[0] != 0)
        printf("    IPv6: %s\n", netlink_format_ip_addr(AF_INET6, intf, ipbuf));
    else
        printf("    IPv6: not set\n");
    printf("     MAC: %s\n\n", netlink_format_mac_addr(buf, intf->mac));

    printf("    mac2str test for %s: |%s|\n", intf->name, netlink_interfaces_mac2str(intf->name));
    printf("     ip2str test for %s: |%s|\n", intf->name, netlink_interfaces_ip2str(intf->name));

    printf("----------------------------------------------------------------\n");

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
