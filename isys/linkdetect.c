/*
 * linkdetect.c - simple link detection
 *
 * heavily based on mii-tool.c from net-tools, just cut down to what we need
 * for anaconda
 *
 * Copyright 2002 Red Hat, Inc.
 * Copyright 2000 David A. Hinds -- dhinds@pcmcia.sourceforge.org
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


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>

#include <sys/socket.h>
#include <sys/types.h>

#include <net/if.h>

#include "mii.h"

static struct ifreq ifr;

static int mdio_read(int skfd, int location)
{
    struct mii_data *mii = (struct mii_data *)&ifr.ifr_data;
    mii->reg_num = location;
    if (ioctl(skfd, SIOCGMIIREG, &ifr) < 0) {
	fprintf(stderr, "SIOCGMIIREG on %s failed: %s\n", ifr.ifr_name,
		strerror(errno));
	return -1;
    }
    return mii->val_out;
}

/* we don't need writing right now */
#if 0
static void mdio_write(int skfd, int location, int value)
{
    struct mii_data *mii = (struct mii_data *)&ifr.ifr_data;
    mii->reg_num = location;
    mii->val_in = value;
    if (ioctl(skfd, SIOCSMIIREG, &ifr) < 0) {
	fprintf(stderr, "SIOCSMIIREG on %s failed: %s\n", ifr.ifr_name,
		strerror(errno));
    }
}
#endif



int get_link_status(char *ifname) {
    struct mii_data *mii = (struct mii_data *)&ifr.ifr_data;
    int sock, i, mii_val[32];

    if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        fprintf(stderr, "Error creating socket: %s\n", strerror(errno));
        return -1;
    }

    /* Get the vitals from the interface. */
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ);
    if (ioctl(sock, SIOCGMIIPHY, &ifr) < 0) {
	if (errno != ENODEV)
	    fprintf(stderr, "SIOCGMIIPHY on '%s' failed: %s\n",
		    ifname, strerror(errno));
	return -1;
    }

    /* Some bits in the BMSR are latched, but we can't rely on being
       the only reader, so only the current values are meaningful */
    mdio_read(sock, MII_BMSR);
    for (i = 0; i < 8; i++)
	mii_val[i] = mdio_read(sock, i);

    if (mii_val[MII_BMCR] == 0xffff) {
	fprintf(stderr, "  No MII transceiver present!.\n");
	return -1;
    }

    if (mii_val[MII_BMSR] & MII_BMSR_LINK_VALID)
        return 1;
    else
        return 0;
}

#ifdef STANDALONE
/* hooray for stupid test programs! */
int main(int argc, char **argv) {
    printf("link status of eth0 is %d\n", get_link_status("eth0"));
}
#endif
