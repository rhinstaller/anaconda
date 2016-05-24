/*
 * Copyright (C) 2013  Red Hat, Inc.
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

#ifndef _WIDGETS_COMMON_H
#define _WIDGETS_COMMON_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_RESOURCE_PATH  "/org/fedoraproject/anaconda/widgets/"

G_GNUC_INTERNAL void anaconda_widget_apply_stylesheet(GtkWidget *widget, const gchar *name);

void anaconda_apply_language(GtkLabel *label, const gchar *language);

G_END_DECLS

#endif
