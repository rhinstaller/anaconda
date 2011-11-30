/*
 * Copyright (C) 2011  Red Hat, Inc.
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
 * Author: Ales Kozumplik <akozumpl@redhat.com>
 */

#ifndef LIGHTBOX_H
#define LIGHTBOX_H

#include <gtk/gtk.h>

GtkWindow *anaconda_lb_show_over(GtkWindow *window);
void       anaconda_lb_destroy(GtkWindow *lightbox);

#endif
