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

#include <math.h>
#include <gtk/gtkgc.h>
#include "gnome-canvas-dot.h"


/* Object argument IDs */
enum {
	ARG_0,
	ARG_X,
	ARG_Y,
	ARG_DIAMETER_PIXELS,
	ARG_FILL_COLOR
};


static void gnome_canvas_dot_class_init (GnomeCanvasDotClass *class);
static void gnome_canvas_dot_init       (GnomeCanvasDot *dot);
static void gnome_canvas_dot_destroy    (GtkObject *object);
static void gnome_canvas_dot_set_arg    (GtkObject *object, GtkArg *arg, guint arg_id);
static void gnome_canvas_dot_get_arg    (GtkObject *object, GtkArg *arg, guint arg_id);

static void gnome_canvas_dot_update    (GnomeCanvasItem *item, double *affine,
					ArtSVP *clip_svp, int flags);
static void gnome_canvas_dot_realize   (GnomeCanvasItem *item);
static void gnome_canvas_dot_unrealize (GnomeCanvasItem *item);
static void gnome_canvas_dot_draw      (GnomeCanvasItem *item, GdkDrawable *drawable,
					int x, int y, int width, int height);
static double gnome_canvas_dot_point   (GnomeCanvasItem *item, double x, double y, int cx, int cy,
					GnomeCanvasItem **actual_item);
static void gnome_canvas_dot_bounds    (GnomeCanvasItem *item,
					double *x1, double *y1, double *x2, double *y2);


static GnomeCanvasItemClass *parent_class;


/* Private data of the GnomeCanvasDot structure */
typedef struct {
	double x, y;
	guint diameter;

	guint fill_color;

	GdkGC *gc;

	guint need_shape_update : 1;
	guint need_color_update : 1;
} DotPrivate;


/**
 * gnome_canvas_dot_get_type:
 * @void:
 *
 * Registers the &GnomeCanvasDot class if necessary, and returns the type ID
 * associated to it.
 *
 * Return value: The type ID of the &GnomeCanvasDot class.
 **/
GtkType
gnome_canvas_dot_get_type (void)
{
	static GtkType dot_type = 0;

	if (!dot_type) {
		static const GtkTypeInfo dot_info = {
			"GnomeCanvasDot",
			sizeof (GnomeCanvasDot),
			sizeof (GnomeCanvasDotClass),
			(GtkClassInitFunc) gnome_canvas_dot_class_init,
			(GtkObjectInitFunc) gnome_canvas_dot_init,
			NULL, /* reserved_1 */
			NULL, /* reserved_2 */
			(GtkClassInitFunc) NULL
		};

		dot_type = gtk_type_unique (gnome_canvas_item_get_type (), &dot_info);
	}

	return dot_type;
}


/* Class initialization function for the dot item */
static void
gnome_canvas_dot_class_init (GnomeCanvasDotClass *class)
{
	GtkObjectClass *object_class;
	GnomeCanvasItemClass *item_class;

	object_class = (GtkObjectClass *) class;
	item_class = (GnomeCanvasItemClass *) class;

	parent_class = gtk_type_class (gnome_canvas_item_get_type ());

	gtk_object_add_arg_type ("GnomeCanvasDot::x",
				 GTK_TYPE_DOUBLE, GTK_ARG_READWRITE, ARG_X);
	gtk_object_add_arg_type ("GnomeCanvasDot::y",
				 GTK_TYPE_DOUBLE, GTK_ARG_READWRITE, ARG_Y);
	gtk_object_add_arg_type ("GnomeCanvasDot::diameter_pixels",
				 GTK_TYPE_UINT, GTK_ARG_READWRITE, ARG_DIAMETER_PIXELS);
	gtk_object_add_arg_type ("GnomeCanvasDot::fill_color",
				 GTK_TYPE_STRING, GTK_ARG_WRITABLE, ARG_FILL_COLOR);

	object_class->destroy = gnome_canvas_dot_destroy;
	object_class->set_arg = gnome_canvas_dot_set_arg;
	object_class->get_arg = gnome_canvas_dot_get_arg;

	item_class->update = gnome_canvas_dot_update;
	item_class->realize = gnome_canvas_dot_realize;
	item_class->unrealize = gnome_canvas_dot_unrealize;
	item_class->draw = gnome_canvas_dot_draw;
	item_class->point = gnome_canvas_dot_point;
	item_class->bounds = gnome_canvas_dot_bounds;
}

/* Object initialization function for the dot item */
static void
gnome_canvas_dot_init (GnomeCanvasDot *dot)
{
	DotPrivate *priv;

	priv = g_new0 (DotPrivate, 1);
	dot->priv = priv;

	priv->x = 0.0;
	priv->y = 0.0;
	priv->fill_color = 0x000000ff;
	priv->need_shape_update = TRUE;
	priv->need_color_update = TRUE;
}

/* Destroy handler for the dot item */
static void
gnome_canvas_dot_destroy (GtkObject *object)
{
	GnomeCanvasDot *dot;
	GnomeCanvasItem *item;
	DotPrivate *priv;

	g_return_if_fail (object != NULL);
	g_return_if_fail (GNOME_IS_CANVAS_DOT (object));

	dot = GNOME_CANVAS_DOT (object);
	item = GNOME_CANVAS_ITEM (object);
	priv = dot->priv;

	gnome_canvas_request_redraw (item->canvas, item->x1, item->y1, item->x2, item->y2);
	g_free (priv);

	if (GTK_OBJECT_CLASS (parent_class)->destroy)
		(* GTK_OBJECT_CLASS (parent_class)->destroy) (object);
}

/* Set_arg handler for the dot item */
static void
gnome_canvas_dot_set_arg (GtkObject *object, GtkArg *arg, guint arg_id)
{
	GnomeCanvasItem *item;
	GnomeCanvasDot *dot;
	DotPrivate *priv;
	char *str;
	GdkColor color;

	item = GNOME_CANVAS_ITEM (object);
	dot = GNOME_CANVAS_DOT (object);
	priv = dot->priv;

	switch (arg_id) {
	case ARG_X:
		priv->x = GTK_VALUE_DOUBLE (*arg);
		priv->need_shape_update = TRUE;
		gnome_canvas_item_request_update (item);
		break;

	case ARG_Y:
		priv->y = GTK_VALUE_DOUBLE (*arg);
		priv->need_shape_update = TRUE;
		gnome_canvas_item_request_update (item);
		break;

	case ARG_DIAMETER_PIXELS:
		priv->diameter = GTK_VALUE_UINT (*arg);
		priv->need_shape_update = TRUE;
		gnome_canvas_item_request_update (item);
		break;

	case ARG_FILL_COLOR:
		str = GTK_VALUE_STRING (*arg);
		g_return_if_fail (str != NULL);

		if (gdk_color_parse (str, &color)) {
			priv->fill_color = ((color.red & 0xff00) << 16 |
					    (color.green & 0xff00) << 8 |
					    (color.blue & 0xff00) |
					    0xff);
			priv->need_color_update = TRUE;
			gnome_canvas_item_request_update (item);
		}

		break;

	default:
		break;
	}
}

/* Get_arg handler for the dot item */
static void
gnome_canvas_dot_get_arg (GtkObject *object, GtkArg *arg, guint arg_id)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;

	dot = GNOME_CANVAS_DOT (object);
	priv = dot->priv;

	switch (arg_id) {
	case ARG_X:
		GTK_VALUE_DOUBLE (*arg) = priv->x;
		break;

	case ARG_Y:
		GTK_VALUE_DOUBLE (*arg) = priv->y;
		break;

	case ARG_DIAMETER_PIXELS:
		GTK_VALUE_UINT (*arg) = priv->diameter;
		break;

	default:
		arg->type = GTK_TYPE_INVALID;
		break;
	}
}

/* Update handler for the dot item */
static void
gnome_canvas_dot_update (GnomeCanvasItem *item, double *affine, ArtSVP *clip_svp, int flags)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	if (parent_class->update)
		(* parent_class->update) (item, affine, clip_svp, flags);

	/* Redraw old area if necessary */

	if (((flags & GNOME_CANVAS_UPDATE_VISIBILITY)
	     && !(GTK_OBJECT_FLAGS (item) & GNOME_CANVAS_ITEM_VISIBLE))
	    || (flags & GNOME_CANVAS_UPDATE_AFFINE)
	    || priv->need_shape_update)
		gnome_canvas_request_redraw (item->canvas, item->x1, item->y1, item->x2, item->y2);

	/* Update color if needed */
	if (priv->need_color_update) {
		GdkGCValues values;
		int mask;

		if (priv->gc)
			gtk_gc_release (priv->gc);

		values.foreground.pixel = gnome_canvas_get_color_pixel (item->canvas,
									priv->fill_color);
		mask = GDK_GC_FOREGROUND;

		priv->gc = gtk_gc_get (gtk_widget_get_visual (GTK_WIDGET (item->canvas))->depth,
				       gtk_widget_get_colormap (GTK_WIDGET (item->canvas)),
				       &values,
				       mask);

		priv->need_color_update = FALSE;
	}

	/* If we need a shape update, or if the item changed visibility
	 * to shown, recompute the bounding box.
	 */
	if (priv->need_shape_update
	    || ((flags & GNOME_CANVAS_UPDATE_VISIBILITY)
		&& (GTK_OBJECT_FLAGS (item) & GNOME_CANVAS_ITEM_VISIBLE))
	    || (flags & GNOME_CANVAS_UPDATE_AFFINE)) {
		ArtPoint i1, i2, c1, c2;
		double d;
		double i2c[6];

		d = priv->diameter / item->canvas->pixels_per_unit;

		i1.x = priv->x - d / 2;
		i1.y = priv->y - d / 2;
		i2.x = priv->x + d / 2;
		i2.y = priv->y + d / 2;

		gnome_canvas_item_i2c_affine (item, i2c);
		art_affine_point (&c1, &i1, i2c);
		art_affine_point (&c2, &i2, i2c);

		item->x1 = c1.x;
		item->y1 = c1.y;
		item->x2 = c2.x + 1;
		item->y2 = c2.y + 1;

		priv->need_shape_update = FALSE;
	}

	/* If the fill our outline changed, we need to redraw, anyways */
	gnome_canvas_request_redraw (item->canvas, item->x1, item->y1, item->x2, item->y2);
}

/* Realize handler for the dot item */
static void
gnome_canvas_dot_realize (GnomeCanvasItem *item)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	if (parent_class->realize)
	    (* parent_class->realize) (item);

	priv->need_color_update = TRUE;
	gnome_canvas_item_request_update (item);
}

/* Unrealize handler for the dot item */
static void
gnome_canvas_dot_unrealize (GnomeCanvasItem *item)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	if (priv->gc) {
		gtk_gc_release (priv->gc);
		priv->gc = NULL;
	}

	if (parent_class->unrealize)
		(* parent_class->unrealize) (item);
}

/* Draw handler for the dot item */
static void
gnome_canvas_dot_draw (GnomeCanvasItem *item, GdkDrawable *drawable,
		       int x, int y, int width, int height)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;
	double i2c[6];
	ArtPoint i, c;
	int x1, y1;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	i.x = priv->x;
	i.y = priv->y;

	gnome_canvas_item_i2c_affine (item, i2c);
	art_affine_point (&c, &i, i2c);

	x1 = floor (c.x - priv->diameter / 2.0 + 0.5) - x;
	y1 = floor (c.y - priv->diameter / 2.0 + 0.5) - y;

	gdk_draw_arc (drawable,
		      priv->gc,
		      TRUE,
		      x1, y1,
		      priv->diameter,
		      priv->diameter,
		      0 * 64,
		      360 * 64);

	gdk_draw_arc (drawable,
		      priv->gc,
		      FALSE,
		      x1, y1,
		      priv->diameter,
		      priv->diameter,
		      0 * 64,
		      360 * 64);
}

/* Point handler for the dot item */
static double
gnome_canvas_dot_point (GnomeCanvasItem *item, double x, double y, int cx, int cy,
			GnomeCanvasItem **actual_item)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;
	double d;
	double dx, dy, dist;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	*actual_item = item;

	d = priv->diameter / item->canvas->pixels_per_unit;

	dx = x - priv->x;
	dy = y - priv->y;
	dist = sqrt (dx * dx + dy * dy);

	if (dist <= d / 2.0)
		return 0.0;
	else
		return dist - d / 2.0;
}

/* Bounds handler for the dot item */
static void
gnome_canvas_dot_bounds (GnomeCanvasItem *item, double *x1, double *y1, double *x2, double *y2)
{
	GnomeCanvasDot *dot;
	DotPrivate *priv;
	double d;

	dot = GNOME_CANVAS_DOT (item);
	priv = dot->priv;

	d = priv->diameter / item->canvas->pixels_per_unit;

	*x1 = priv->x - d / 2.0;
	*y1 = priv->y - d / 2.0;
	*x2 = priv->x + d / 2.0;
	*y2 = priv->y + d / 2.0;
}
