/*
 * fwloader.h -- a small firmware loader.
 *
 * Copyright (C) 2006, 2007  Red Hat, Inc.  All rights reserved.
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
 *
 * Author(s): Peter Jones <pjones@redhat.com>
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
