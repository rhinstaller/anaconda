/*
 * auditd.h: This is a simple audit daemon that throws all messages away.
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
 */

#ifndef ISYS_AUDIT_H
#define ISYS_AUDIT_H 1

extern int audit_daemonize(void);

#endif /* ISYS_AUDIT_H */
/*
 * vim:ts=8:sw=4:sts=4:et
 */
