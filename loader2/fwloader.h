/*
 * fwloader.h -- a small firmware loader.
 *
 * Peter Jones (pjones@redhat.com)
 *
 * Copyright 2006-2007 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * General Public License, version 2.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */


#ifndef FWLOADER_H
#define FWLOADER_H 1

#include "loader.h"

extern void set_fw_search_path(struct loaderData_s *loaderData, char *path);
extern void add_fw_search_dir(struct loaderData_s *loaderData, char *dir);
extern void start_fw_loader(struct loaderData_s *loaderData);
extern void stop_fw_loader(struct loaderData_s *loaderData);

#endif /* FWLOADER_H */
/*
 * vim:ts=8:sw=4:sts=4:et
 */
