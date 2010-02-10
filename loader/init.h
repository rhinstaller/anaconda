/*
 * init.h
 *
 * Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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
#ifndef INIT_H
#define INIT_H

typedef enum {
	REBOOT,
	POWEROFF,
	HALT,
        /* gives user a chance to read the trace before scrolling the text out
           with disk unmounting and termination info */
        DELAYED_REBOOT
} reboot_action;

#endif /* INIT_H */
