/*
 * auditd.h
 *
 * This is a simple audit daemon that throws all messages away.
 *
 * Peter Jones <pjones@redhat.com>
 *
 * Copyright 2006 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License, version 2.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#ifndef ISYS_AUDIT_H
#define ISYS_AUDIT_H 1

extern int audit_daemonize(void);

#endif /* ISYS_AUDIT_H */
/*
 * vim:ts=8:sw=4:sts=4:et
 */
