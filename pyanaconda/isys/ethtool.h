/*
 * net.h
 *
 * Copyright (C) 2007  Red Hat, Inc.  All rights reserved.
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
 */

#ifndef ISYSNET_H
#define ISYSNET_H

#include <linux/types.h>
#include <linux/ethtool.h>

/* returns 1 for link, 0 for no link, -1 for unknown */
int get_link_status(char *ifname);

typedef enum ethtool_speed_t { ETHTOOL_SPEED_UNSPEC = -1, 
                               ETHTOOL_SPEED_10 = SPEED_10, 
                               ETHTOOL_SPEED_100 = SPEED_100,
                               ETHTOOL_SPEED_1000 = SPEED_1000 } ethtool_speed;
typedef enum ethtool_duplex_t { ETHTOOL_DUPLEX_UNSPEC = -1, 
                                ETHTOOL_DUPLEX_HALF = DUPLEX_HALF,
                                ETHTOOL_DUPLEX_FULL = DUPLEX_FULL } ethtool_duplex;

/* set ethtool settings */
int setEthtoolSettings(char * dev, ethtool_speed speed, ethtool_duplex duplex);
int identifyNIC(char *iface, int seconds);

#endif
