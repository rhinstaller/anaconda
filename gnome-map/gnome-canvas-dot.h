/* Dot item for the GNOME canvas
 *
 * Copyright (C) 1999 Red Hat, Inc.
 *
 * Author: Federico Mena <federico@redhat.com>
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
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

#ifndef GNOME_CANVAS_DOT_H
#define GNOME_CANVAS_DOT_H

#include <libgnome/gnome-defs.h>
#include <libgnomeui/gnome-canvas.h>


BEGIN_GNOME_DECLS


#define GNOME_TYPE_CANVAS_DOT            (gnome_canvas_dot_get_type ())
#define GNOME_CANVAS_DOT(obj)            (GTK_CHECK_CAST ((obj), GNOME_TYPE_CANVAS_DOT,		\
							  GnomeCanvasDot))
#define GNOME_CANVAS_DOT_CLASS(klass)    (GTK_CHECK_CLASS_CAST ((klass), GNOME_TYPE_CANVAS_DOT,	\
								GnomeCanvasDotClass))
#define GNOME_IS_CANVAS_DOT(obj)         (GTK_CHECK_TYPE ((obj), GNOME_TYPE_CANVAS_DOT))
#define GNOME_IS_CANVAS_DOT_CLASS(klass) (GTK_CHECK_CLASS_TYPE ((klass), GNOME_TYPE_CANVAS_DOT))


typedef struct _GnomeCanvasDot GnomeCanvasDot;
typedef struct _GnomeCanvasDotClass GnomeCanvasDotClass;

struct _GnomeCanvasDot {
	GnomeCanvasItem item;

	gpointer priv;
};

struct _GnomeCanvasDotClass {
	GnomeCanvasItemClass parent_class;
};


GtkType gnome_canvas_dot_get_type (void);


END_GNOME_DECLS

#endif
