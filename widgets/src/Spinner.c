/*
 * Copyright (C) 2014 Red Hat, Inc. (www.redhat.com)
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
 * for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, see <http://www.gnu.org/licenses/>.
 *
 * Authors: Milan Crha <mcrha@redhat.com>
 */

/* NOTE FROM ANACONDA:
 * This widget is a search/replace of ESpinner from Evolution (LGPL, see
 * above), because GtkSpinner doesn't run so good in a VM. See
 * https://bugzilla.gnome.org/show_bug.cgi?id=732180 and
 * https://bugzilla.gnome.org/show_bug.cgi?id=732199.
 *
 * The source of the animation is a PNG containing each frame to animate,
 * arranged in a 7x5 grid. It was created with Inkscape by doing the following:
 *  - Load process-working-symbolic.svg from adwaita-icon-theme
 *  - In File->Document Properties, change the background to transparent (alpha 0)
 *  - Select the spinner, Edit->Clone->Create Tiled Clones...
 *    * Set the clone to 5x7 rows, columns
 *    * There's a rotation option here, but it acted kind of weird, so I left it alone
 *  - Rotate each object by the appropriate multiple of 360 / 35 degrees using Object->Transform
 *    * You can select more than one at once with shift+click so it doesn't take that long
 *  - File->Export PNG Image...
 *    * Choose Drawing, and 112x80 for the image size
 *    * Size has to match FRAME_SIZE below
 */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <gtk/gtk.h>

#include "Spinner.h"
#include "widgets-common.h"

#define MAIN_IMAGE_FILENAME	"working.png"
#define FRAME_SIZE		16
#define FRAME_TIMEOUT_MS	100

struct _AnacondaSpinnerPrivate
{
	GSList *pixbufs;
	GSList *current_frame; /* link of 'pixbufs' */
	gboolean active;
	guint timeout_id;
};

enum {
	PROP_0,
	PROP_ACTIVE
};

G_DEFINE_TYPE (AnacondaSpinner, anaconda_spinner, GTK_TYPE_IMAGE)

static gboolean
anaconda_spinner_update_frame_cb (gpointer user_data)
{
	AnacondaSpinner *spinner = user_data;

	g_return_val_if_fail (ANACONDA_IS_SPINNER (spinner), FALSE);

	if (spinner->priv->current_frame)
		spinner->priv->current_frame = spinner->priv->current_frame->next;
	if (!spinner->priv->current_frame)
		spinner->priv->current_frame = spinner->priv->pixbufs;

	if (!spinner->priv->current_frame) {
		g_warn_if_reached ();
		return FALSE;
	}

	gtk_image_set_from_pixbuf (GTK_IMAGE (spinner), spinner->priv->current_frame->data);

	return TRUE;
}

static void
anaconda_spinner_enable_spin (AnacondaSpinner *spinner)
{
	spinner->priv->timeout_id = g_timeout_add_full (G_PRIORITY_LOW, FRAME_TIMEOUT_MS, anaconda_spinner_update_frame_cb, spinner, NULL);
}

static void
anaconda_spinner_disable_spin (AnacondaSpinner *spinner)
{
	if (spinner->priv->timeout_id)
	{
		g_source_remove (spinner->priv->timeout_id);
		spinner->priv->timeout_id = 0;
	}
}

static void
anaconda_spinner_set_property (GObject *object,
			guint property_id,
			const GValue *value,
			GParamSpec *pspec)
{
	switch (property_id) {
		case PROP_ACTIVE:
			anaconda_spinner_set_active (
				ANACONDA_SPINNER (object),
				g_value_get_boolean (value));
			return;
	}

	G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
}

static void
anaconda_spinner_get_property (GObject *object,
			guint property_id,
			GValue *value,
			GParamSpec *pspec)
{
	switch (property_id) {
		case PROP_ACTIVE:
			g_value_set_boolean (
				value,
				anaconda_spinner_get_active (ANACONDA_SPINNER (object)));
			return;
	}

	G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
}

static void
anaconda_spinner_constructed (GObject *object)
{
	AnacondaSpinner *spinner;
	GdkPixbuf *main_pixbuf;
	gint xx, yy, width, height;
	GError *error = NULL;
        gchar *filename;

	/* Chain up to parent's method. */
	G_OBJECT_CLASS (anaconda_spinner_parent_class)->constructed (object);

	spinner = ANACONDA_SPINNER (object);

        filename = g_strdup_printf("%s/pixmaps/%s", anaconda_get_widgets_datadir(), MAIN_IMAGE_FILENAME);
        main_pixbuf = gdk_pixbuf_new_from_file (filename, &error);
        g_free(filename);

	if (!main_pixbuf) {
		g_warning ("%s: Failed to load image: %s", error ? error->message : "Unknown error", G_STRFUNC);
		g_clear_error (&error);
		return;
	}

	width = gdk_pixbuf_get_width (main_pixbuf);
	height = gdk_pixbuf_get_height (main_pixbuf);

	for (yy = 0; yy < height; yy += FRAME_SIZE) {
		for (xx = 0; xx < width; xx+= FRAME_SIZE) {
			GdkPixbuf *frame;

			frame = gdk_pixbuf_new_subpixbuf (main_pixbuf, xx, yy, FRAME_SIZE, FRAME_SIZE);
			if (frame)
				spinner->priv->pixbufs = g_slist_prepend (spinner->priv->pixbufs, frame);
		}
	}

	g_object_unref (main_pixbuf);

	spinner->priv->pixbufs = g_slist_reverse (spinner->priv->pixbufs);

	spinner->priv->current_frame = spinner->priv->pixbufs;
	if (spinner->priv->pixbufs)
		gtk_image_set_from_pixbuf (GTK_IMAGE (spinner), spinner->priv->pixbufs->data);
}

static void
anaconda_spinner_dispose (GObject *object)
{
	/* This resets the timeout_id too */
	anaconda_spinner_set_active (ANACONDA_SPINNER (object), FALSE);

	/* Chain up to parent's method. */
	G_OBJECT_CLASS (anaconda_spinner_parent_class)->dispose (object);
}

static void
anaconda_spinner_finalize (GObject *object)
{
	AnacondaSpinner *spinner = ANACONDA_SPINNER (object);

	g_slist_free_full (spinner->priv->pixbufs, g_object_unref);
	spinner->priv->pixbufs = NULL;
	spinner->priv->current_frame = NULL;

	g_warn_if_fail (spinner->priv->timeout_id == 0);

	/* Chain up to parent's method. */
	G_OBJECT_CLASS (anaconda_spinner_parent_class)->finalize (object);
}

static void
anaconda_spinner_realize (GtkWidget *widget)
{
	AnacondaSpinner *spinner = ANACONDA_SPINNER(widget);

	/* Chain up to the parent class first, then enable the spinner
	 * after the widget is realized
	 */
        GTK_WIDGET_CLASS(anaconda_spinner_parent_class)->realize(widget);

	if (spinner->priv->active)
	{
		anaconda_spinner_enable_spin(spinner);
	}
}

static void
anaconda_spinner_unrealize (GtkWidget *widget)
{
	AnacondaSpinner *spinner = ANACONDA_SPINNER(widget);

	/* Disable the spinner before chaining up to the parent class */
	anaconda_spinner_disable_spin(spinner);

        GTK_WIDGET_CLASS(anaconda_spinner_parent_class)->unrealize(widget);
}

static void
anaconda_spinner_class_init (AnacondaSpinnerClass *klass)
{
	GObjectClass *object_class;
        GtkWidgetClass *widget_class;

	g_type_class_add_private (klass, sizeof (AnacondaSpinnerPrivate));

	object_class = G_OBJECT_CLASS (klass);
	object_class->set_property = anaconda_spinner_set_property;
	object_class->get_property = anaconda_spinner_get_property;
	object_class->dispose = anaconda_spinner_dispose;
	object_class->finalize = anaconda_spinner_finalize;
	object_class->constructed = anaconda_spinner_constructed;

        widget_class = GTK_WIDGET_CLASS(klass);
        widget_class->realize = anaconda_spinner_realize;
        widget_class->unrealize = anaconda_spinner_unrealize;

	/**
	 * AnacondaSpinner:active:
	 *
	 * Whether the animation is active.
	 **/
	g_object_class_install_property (
		object_class,
		PROP_ACTIVE,
		g_param_spec_boolean (
			"active",
			"Active",
			"Whether the animation is active",
			FALSE,
			G_PARAM_READWRITE |
			G_PARAM_CONSTRUCT |
			G_PARAM_STATIC_STRINGS));
}

static void
anaconda_spinner_init (AnacondaSpinner *spinner)
{
	spinner->priv = G_TYPE_INSTANCE_GET_PRIVATE (spinner, ANACONDA_TYPE_SPINNER, AnacondaSpinnerPrivate);
}

GtkWidget *
anaconda_spinner_new (void)
{
	return g_object_new (ANACONDA_TYPE_SPINNER, NULL);
}

gboolean
anaconda_spinner_get_active (AnacondaSpinner *spinner)
{
	g_return_val_if_fail (ANACONDA_IS_SPINNER (spinner), FALSE);

	return spinner->priv->active;
}

void
anaconda_spinner_set_active (AnacondaSpinner *spinner,
		      gboolean active)
{
	g_return_if_fail (ANACONDA_IS_SPINNER (spinner));

	if ((spinner->priv->active ? 1 : 0) == (active ? 1 : 0))
		return;

	spinner->priv->active = active;

	if (gtk_widget_get_realized(GTK_WIDGET(spinner)))
	{
		if (active)
		{
			anaconda_spinner_enable_spin (spinner);
		}
		else
		{
			anaconda_spinner_disable_spin (spinner);
		}
	}

	g_object_notify (G_OBJECT (spinner), "active");
}

void
anaconda_spinner_start (AnacondaSpinner *spinner)
{
	anaconda_spinner_set_active (spinner, TRUE);
}

void
anaconda_spinner_stop (AnacondaSpinner *spinner)
{
	anaconda_spinner_set_active (spinner, FALSE);
}
