/*
 * Copyright (C) 2014  Red Hat, Inc.
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
 * Author: David Shea <dshea@redhat.com>
 */

#ifndef _BASE_STANDALONE_H
#define _BASE_STANDALONE_H

#include <gtk/gtk.h>

#include "BaseWindow.h"

G_BEGIN_DECLS

#define ANACONDA_TYPE_BASE_STANDALONE            (anaconda_base_standalone_get_type())
#define ANACONDA_BASE_STANDALONE(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), ANACONDA_TYPE_BASE_STANDALONE, AnacondaBaseStandalone))
#define ANACONDA_IS_BASE_STANDALONE(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), ANACONDA_TYPE_BASE_STANDALONE))
#define ANACONDA_BASE_STANDALONE_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass), ANACONDA_TYPE_BASE_STANDALONE, AnacondaBaseStandaloneClass))
#define ANACONDA_IS_BASE_STANDALONE_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass), ANACONDA_TYPE_BASE_STANDALONE))
#define ANACONDA_BASE_STANDALONE_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj), ANACONDA_TYPE_BASE_STANDALONE, AnacondaBaseStandaloneClass))

typedef struct _AnacondaBaseStandalone        AnacondaBaseStandalone;
typedef struct _AnacondaBaseStandaloneClass   AnacondaBaseStandaloneClass;
typedef struct _AnacondaBaseStandalonePrivate AnacondaBaseStandalonePrivate;

/**
 * AnacondaBaseStandalone:
 *
 * The AnacondaBaseStandalone class contains only private fields and should not
 * be directly accessed.
 */
struct _AnacondaBaseStandalone {
    AnacondaBaseWindow             parent;

    /*< private >*/
    AnacondaBaseStandalonePrivate *priv;
};

/**
 * AnacondaBaseStandaloneClass:
 * @parent_class: The object class structure needs to be the first element in
 *                the widget class structure in order for the class mechanism
 *                to work correctly. This allows a AnacondaBaseStandaloneClass
 *                pointer to be cast to a #AnacondaBaseWindowClass pointer.
 * @quit_clicked: Function pointer called when the #AnacondaBaseStandalone::quit-clicked
 *                signal is emitted.
 * @continue_clicked: Function pointer called when the #AnacondaBaseStandalone::continue-clicked
 *                    signal is emitted.
 */
struct _AnacondaBaseStandaloneClass {
    AnacondaBaseWindowClass parent_class;

    void (* quit_clicked)     (AnacondaBaseStandalone *window);
    void (* continue_clicked) (AnacondaBaseStandalone *window);
};

GType       anaconda_base_standalone_get_type(void);

gboolean    anaconda_base_standalone_get_may_continue(AnacondaBaseStandalone *win);
void        anaconda_base_standalone_set_may_continue(AnacondaBaseStandalone *win, gboolean may_continue);

GtkButton * anaconda_base_standalone_get_quit_button(AnacondaBaseStandalone *win);
GtkButton * anaconda_base_standalone_get_continue_button(AnacondaBaseStandalone *win);

G_END_DECLS

#endif
