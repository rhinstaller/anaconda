/*
 * mii.h 1.4 2000/04/25 22:06:15
 *
 * Media Independent Interface support: register layout and ioctl's
 *
 * Copyright (C) 2000 David A. Hinds -- dhinds@pcmcia.sourceforge.org
 */

#ifndef _LINUX_MII_H
#define _LINUX_MII_H

/* network interface ioctl's for MII commands */
#ifndef SIOCGMIIPHY
#define SIOCGMIIPHY 0x8947 	/* Read from current PHY */
#define SIOCGMIIREG 0x8948 	/* Read any PHY register */
#define SIOCSMIIREG 0x8949 	/* Write any PHY register */
#endif

#include <linux/types.h>

/* This data structure is used for all the MII ioctl's */
struct mii_data {
    __u16	phy_id;
    __u16	reg_num;
    __u16	val_in;
    __u16	val_out;
};

/* Basic Mode Control Register */
#define MII_BMCR		0x00
#define  MII_BMCR_RESET		0x8000
#define  MII_BMCR_LOOPBACK	0x4000
#define  MII_BMCR_100MBIT	0x2000
#define  MII_BMCR_AN_ENA	0x1000
#define  MII_BMCR_ISOLATE	0x0400
#define  MII_BMCR_RESTART	0x0200
#define  MII_BMCR_DUPLEX	0x0100
#define  MII_BMCR_COLTEST	0x0080

/* Basic Mode Status Register */
#define MII_BMSR		0x01
#define  MII_BMSR_CAP_MASK	0xf800
#define  MII_BMSR_100BASET4	0x8000
#define  MII_BMSR_100BASETX_FD	0x4000
#define  MII_BMSR_100BASETX_HD	0x2000
#define  MII_BMSR_10BASET_FD	0x1000
#define  MII_BMSR_10BASET_HD	0x0800
#define  MII_BMSR_NO_PREAMBLE	0x0040
#define  MII_BMSR_AN_COMPLETE	0x0020
#define  MII_BMSR_REMOTE_FAULT	0x0010
#define  MII_BMSR_AN_ABLE	0x0008
#define  MII_BMSR_LINK_VALID	0x0004
#define  MII_BMSR_JABBER	0x0002
#define  MII_BMSR_EXT_CAP	0x0001

#define MII_PHY_ID1		0x02
#define MII_PHY_ID2		0x03

/* Auto-Negotiation Advertisement Register */
#define MII_ANAR		0x04
/* Auto-Negotiation Link Partner Ability Register */
#define MII_ANLPAR		0x05
#define  MII_AN_NEXT_PAGE	0x8000
#define  MII_AN_ACK		0x4000
#define  MII_AN_REMOTE_FAULT	0x2000
#define  MII_AN_ABILITY_MASK	0x07e0
#define  MII_AN_FLOW_CONTROL	0x0400
#define  MII_AN_100BASET4	0x0200
#define  MII_AN_100BASETX_FD	0x0100
#define  MII_AN_100BASETX_HD	0x0080
#define  MII_AN_10BASET_FD	0x0040
#define  MII_AN_10BASET_HD	0x0020
#define  MII_AN_PROT_MASK	0x001f
#define  MII_AN_PROT_802_3	0x0001

/* Auto-Negotiation Expansion Register */
#define MII_ANER		0x06
#define  MII_ANER_MULT_FAULT	0x0010
#define  MII_ANER_LP_NP_ABLE	0x0008
#define  MII_ANER_NP_ABLE	0x0004
#define  MII_ANER_PAGE_RX	0x0002
#define  MII_ANER_LP_AN_ABLE	0x0001

#endif /* _LINUX_MII_H */
