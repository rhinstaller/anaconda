/*
 * ethtool.c - setting of basic ethtool options
 *
 * Copyright 2003 Red Hat, Inc.
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <net/if.h>

#include <linux/sockios.h>
#include "net.h"

static int set_intf_up(struct ifreq ifr, int sock) {
    if (ioctl(sock, SIOCGIFFLAGS, &ifr) < 0) {
        return (-1);
    }
    ifr.ifr_flags |= (IFF_UP | IFF_RUNNING);
    if (ioctl(sock, SIOCSIFFLAGS, &ifr) < 0) {
        fprintf(stderr, "failed to bring up interface %s: %s", ifr.ifr_name,
                strerror(errno));
        return -1;
    }
    return (0);
}

int setEthtoolSettings(char * dev, ethtool_speed speed, 
                       ethtool_duplex duplex) {
    int sock, err;
    struct ethtool_cmd ecmd;
    struct ifreq ifr;

    if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Unable to create socket");
        return -1;
    }

    /* Setup our control structures. */
    memset(&ifr, 0, sizeof(ifr));
    strcpy(ifr.ifr_name, dev);

    if (set_intf_up(ifr, sock) == -1) {
        fprintf(stderr, "unable to bring up interface %s: %s", dev, 
                strerror(errno));
        return -1;
    }

    ecmd.cmd = ETHTOOL_GSET;
    ifr.ifr_data = (caddr_t)&ecmd;
    err = ioctl(sock, SIOCETHTOOL, &ifr);
    if (err < 0) {
        perror("Unable to get settings via ethtool.  Not setting");
        return -1;
    }

    if (speed != ETHTOOL_SPEED_UNSPEC)
        ecmd.speed = speed;
    if (duplex != ETHTOOL_DUPLEX_UNSPEC)
        ecmd.duplex = duplex;
    if ((duplex != ETHTOOL_DUPLEX_UNSPEC) || (speed != ETHTOOL_SPEED_UNSPEC))
        ecmd.autoneg = AUTONEG_DISABLE;

    ecmd.cmd = ETHTOOL_SSET;
    ifr.ifr_data = (caddr_t)&ecmd;
    err = ioctl(sock, SIOCETHTOOL, &ifr);
    if (err < 0) {
        //        perror("Unable to set settings via ethtool.  Not setting");
        return -1;
    }

    return 0;
}

int identifyNIC(char *iface, int seconds) {
    int sock;
    struct ethtool_value edata;
    struct ifreq ifr;

    if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Unable to create socket");
        return -1;
    }

    memset(&ifr, 0, sizeof(ifr));
    memset(&edata, 0, sizeof(edata));

    strcpy(ifr.ifr_name, iface);
    edata.cmd = ETHTOOL_PHYS_ID;
    edata.data = seconds;
    ifr.ifr_data = (caddr_t) &edata;

    if (ioctl(sock, SIOCETHTOOL, &ifr) < 0) {
        perror("Unable to identify NIC");
    }

    return 0;
}
