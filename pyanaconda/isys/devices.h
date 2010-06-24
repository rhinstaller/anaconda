/*
 * devices.h
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

#ifndef DEVICES_H
#define DEVICES_H

enum deviceType {
    DEVICE_ANY = ~0,
    DEVICE_NETWORK = (1 << 0),
    DEVICE_DISK = (1 << 1),
    DEVICE_CDROM = (1 << 2)
};

struct device {
    char *device;
    char *description;
    enum deviceType type;
    union {
        char *hwaddr;
        int removable;
    } priv;
};

struct device **getDevices(enum deviceType type);

#endif
