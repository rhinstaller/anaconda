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
 * Author: Chris Lumens <clumens@redhat.com>
 */

#ifndef _SPOKE_SELECTOR_H
#define _SPOKE_SELECTOR_H

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_SPOKE_SELECTOR            (anaconda_spoke_selector_get_type())
#define ANACONDA_SPOKE_SELECTOR(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_SPOKE_SELECTOR, AnacondaSpokeSelector))
#define ANACONDA_IS_SPOKE_SELECTOR(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj)), ANACONDA_TYPE_SPOKE_SELECTOR)
#define ANACONDA_SPOKE_SELECTOR_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_SPOKE_SELECTOR, AnacondaSpokeSelectorClass))
#define ANACONDA_IS_SPOKE_SELECTOR_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_SPOKE_SELECTOR))
#define ANACONDA_SPOKE_SELECTOR_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_SPOKE_SELECTOR, AnacondaSpokeSelectorClass))

typedef struct _AnacondaSpokeSelector        AnacondaSpokeSelector;
typedef struct _AnacondaSpokeSelectorClass   AnacondaSpokeSelectorClass;
typedef struct _AnacondaSpokeSelectorPrivate AnacondaSpokeSelectorPrivate;

/**
 * AnacondaSpokeSelector:
 *
 * The AnacondaSpokeSelector struct contains only private fields and should
 * not be directly accessed.
 */
struct _AnacondaSpokeSelector {
    GtkEventBox                   parent;

    /*< private >*/
    AnacondaSpokeSelectorPrivate *priv;
};

/**
 * AnacondaSpokeSelectorClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows an AnacondaSpokeSelectorClass
 *                pointer to be cast to a #GtkEventBox pointer.
 */
struct _AnacondaSpokeSelectorClass {
    GtkEventBoxClass parent_class;
};

GType       anaconda_spoke_selector_get_type (void);
GtkWidget  *anaconda_spoke_selector_new      ();
gboolean    anaconda_spoke_selector_get_incomplete (AnacondaSpokeSelector *spoke);
void        anaconda_spoke_selector_set_incomplete (AnacondaSpokeSelector *spoke, gboolean is_incomplete);

G_END_DECLS

#endif
