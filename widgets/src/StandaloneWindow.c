/*
 * Copyright (C) 2011-2014  Red Hat, Inc.
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

#include "config.h"

#include "BaseStandalone.h"
#include "StandaloneWindow.h"
#include "intl.h"

#include <atk/atk.h>
#include <gdk/gdkkeysyms.h>

/**
 * SECTION: StandaloneWindow
 * @title: AnacondaStandaloneWindow
 * @short_description: Window for displaying standalone spokes
 *
 * A #AnacondaStandaloneWindow is a widget that displays a standalone
 * spoke.  A standalone spoke is like a normal spoke, but is not entered via a
 * hub.  Instead, it is displayed by itself.  Examples include the welcome and
 * network configuration screens at the beginning of installation.
 *
 * The AnacondaStandaloneWindow consist of three areas:
 *
 * - A navigation area in the top of the screen, inherited from #AnacondaBaseWindow.
 *
 * - A button box at the bottom of the screen, with Quit and Continue buttons.
 *   The Continue button may not be enabled until required information is
 *   entered by the user.
 *
 * - An action area in the middle of the screen, taking up a majority of the
 *   space.  This is where widgets will be added and the user will do things.
 */

#define QUIT_TEXT       N_("_Quit")
#define CONTINUE_TEXT   N_("_Continue")

struct _AnacondaStandaloneWindowPrivate {
    GtkWidget  *button_box;
    GtkWidget  *continue_button, *quit_button;
};

enum {
    PROP_QUIT_BUTTON = 1,
    PROP_CONTINUE_BUTTON
};

static void anaconda_standalone_window_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);

G_DEFINE_TYPE(AnacondaStandaloneWindow, anaconda_standalone_window, ANACONDA_TYPE_BASE_STANDALONE)

static void anaconda_standalone_window_class_init(AnacondaStandaloneWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    object_class->get_property = anaconda_standalone_window_get_property;

    /*
     * Override the quit-button and continue-button properties to make them
     * read only. The buttons will be create during the object's init method.
     */

    /**
     * AnacondaStandaloneWindow::quit-button:
     *
     * The button to quit anaconda.
     *
     * This overrides #AnacondaBaseStandalone:quit-button in #AnacondaBaseStandalone to be read-only.
     *
     * Since: 3.0
     */
    g_object_class_install_property(object_class,
                                    PROP_QUIT_BUTTON,
                                    g_param_spec_object("quit-button",
                                                        P_("Quit button"),
                                                        P_("The button to quit Anaconda"),
                                                        GTK_TYPE_BUTTON,
                                                        G_PARAM_READABLE));

    /**
     * AnacondaStandaloneWindow::continue-button:
     *
     * The button to continue to the next window.
     *
     * This overrides #AnacondaBaseStandalone:continue-button in #AnacondaBaseStandalone to be read-only.
     *
     * Since: 3.0
     */
    g_object_class_install_property(object_class,
                                    PROP_CONTINUE_BUTTON,
                                    g_param_spec_object("continue-button",
                                                        P_("Continue button"),
                                                        P_("The button to continue to the next window"),
                                                        GTK_TYPE_BUTTON,
                                                        G_PARAM_READABLE));

    g_type_class_add_private(object_class, sizeof(AnacondaStandaloneWindowPrivate));
}

static void anaconda_standalone_window_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    /* Just chain up to the parent class get_property */
    gchar *parent_property = g_strdup_printf("%s::%s", G_OBJECT_CLASS_NAME(anaconda_standalone_window_parent_class), pspec->name);
    g_object_get_property(object, parent_property, value);
    g_free(parent_property);
}

/**
 * anaconda_standalone_window_new:
 *
 * Creates a new #AnacondaStandaloneWindow, which is a window designed for
 * displaying a standalone spoke, such as the welcome screen or network
 * configuration.
 *
 * Returns: A new #AnacondaStandaloneWindow.
 */
GtkWidget *anaconda_standalone_window_new() {
    return g_object_new(ANACONDA_TYPE_STANDALONE_WINDOW, NULL);
}

static void anaconda_standalone_window_init(AnacondaStandaloneWindow *win) {
    AtkObject *atk;
    GtkWidget *main_box = anaconda_base_window_get_main_box(ANACONDA_BASE_WINDOW(win));
    GtkStyleContext *context;

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_STANDALONE_WINDOW,
                                            AnacondaStandaloneWindowPrivate);

    /* Create the buttons. */
    win->priv->quit_button = gtk_button_new_with_mnemonic(_(QUIT_TEXT));
    atk = gtk_widget_get_accessible(win->priv->quit_button);
    atk_object_set_name(atk, _(QUIT_TEXT));

    win->priv->continue_button = gtk_button_new_with_mnemonic(_(CONTINUE_TEXT));
    atk = gtk_widget_get_accessible(win->priv->continue_button);
    atk_object_set_name(atk, _(CONTINUE_TEXT));

    /* Set the Continue button to the blue 'suggested-action' style class */
    context = gtk_widget_get_style_context(win->priv->continue_button);
    gtk_style_context_add_class(context, "suggested-action");

    /* Set the properties on AnacondaBaseStandalone */
    g_object_set(G_OBJECT(win), "AnacondaBaseStandalone::quit-button", win->priv->quit_button, NULL);
    g_object_set(G_OBJECT(win), "AnacondaBaseStandalone::continue-button", win->priv->continue_button, NULL);

    /* Create the button box and pack the buttons into it. */
    win->priv->button_box = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_widget_set_margin_start(win->priv->button_box, 6);
    gtk_widget_set_margin_end(win->priv->button_box, 6);
    gtk_widget_set_margin_bottom(win->priv->button_box, 6);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(win->priv->button_box), GTK_BUTTONBOX_END);
    gtk_box_set_spacing(GTK_BOX(win->priv->button_box), 12);

    gtk_container_add(GTK_CONTAINER(win->priv->button_box), win->priv->quit_button);
    gtk_container_add(GTK_CONTAINER(win->priv->button_box), win->priv->continue_button);

    gtk_box_pack_start(GTK_BOX(main_box), win->priv->button_box, FALSE, TRUE, 0);
}

/**
 * anaconda_standalone_window_retranslate:
 * @win: a #AnacondaStandaloneWindow
 *
 * Reload translations for this widget as needed.  Generally, this is not
 * needed.  However when changing the language during installation, we need
 * to be able to make sure the screen gets retranslated.  This function is
 * kind of ugly but avoids having to destroy and reload the screen.
 *
 * Since: 1.0
 */
void anaconda_standalone_window_retranslate(AnacondaStandaloneWindow *win) {
    anaconda_base_window_retranslate(ANACONDA_BASE_WINDOW(win));

    gtk_button_set_label(GTK_BUTTON(win->priv->quit_button), _(QUIT_TEXT));
    gtk_button_set_label(GTK_BUTTON(win->priv->continue_button), _(CONTINUE_TEXT));
}
