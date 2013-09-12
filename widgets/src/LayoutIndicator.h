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
 *
 * Author: Vratislav Podzimek <vpodzime@redhat.com>
 */

#ifndef _LAYOUT_INDICATOR_H
#define _LAYOUT_INDICATOR_H

#include <gtk/gtk.h>
#include <libxklavier/xklavier.h>

G_BEGIN_DECLS

#define ANACONDA_TYPE_LAYOUT_INDICATOR            (anaconda_layout_indicator_get_type())
#define ANACONDA_LAYOUT_INDICATOR(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_LAYOUT_INDICATOR, AnacondaLayoutIndicator))
#define ANACONDA_IS_LAYOUT_INDICATOR(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj)), ANACONDA_TYPE_LAYOUT_INDICATOR)
#define ANACONDA_LAYOUT_INDICATOR_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_LAYOUT_INDICATOR, AnacondaLayoutIndicatorClass))
#define ANACONDA_IS_LAYOUT_INDICATOR_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_LAYOUT_INDICATOR))
#define ANACONDA_LAYOUT_INDICATOR_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_LAYOUT_INDICATOR, AnacondaLayoutIndicatorClass))

typedef struct _AnacondaLayoutIndicator        AnacondaLayoutIndicator;
typedef struct _AnacondaLayoutIndicatorClass   AnacondaLayoutIndicatorClass;
typedef struct _AnacondaLayoutIndicatorPrivate AnacondaLayoutIndicatorPrivate;

/**
 * AnacondaLayoutIndicator:
 *
 * The AnacondaLayoutIndicator struct contains only private fields and should
 * not be directly accessed.
 */
struct _AnacondaLayoutIndicator {
    /*< private >*/
    GtkEventBox                   parent;
    AnacondaLayoutIndicatorPrivate *priv;
};

/**
 * AnacondaLayoutIndicatorClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly.  This allows an AnacondaLayoutIndicatorClass
 *                pointer to be cast to a #GtkEventBox pointer.
 * @engine: A singleton XklEngine instance that is used by all instances of
 *          LayoutIndicator.
 */
struct _AnacondaLayoutIndicatorClass {
    GtkEventBoxClass parent_class;

    /* this has to be a class attribute, because XklEngine is a singleton that
       should be used by all instances */
    XklEngine *engine;
};

GType       anaconda_layout_indicator_get_type (void);
GtkWidget  *anaconda_layout_indicator_new      ();

gchar      *anaconda_layout_indicator_get_current_layout (AnacondaLayoutIndicator *indicator);
guint      anaconda_layout_indicator_get_label_width (AnacondaLayoutIndicator *indicator);
void       anaconda_layout_indicator_set_label_width (AnacondaLayoutIndicator *indicator,
                                                       guint new_width);
void       anaconda_layout_indicator_retranslate (AnacondaLayoutIndicator *indicator);

G_END_DECLS

#endif
