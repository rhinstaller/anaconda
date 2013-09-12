/*
 * Copyright (C) 2011-2013  Red Hat, Inc.
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

#include "BaseWindow.h"
#include "StandaloneWindow.h"
#include "intl.h"

#include <gdk/gdkkeysyms.h>

/**
 * SECTION: StandaloneWindow
 * @title: AnacondaStandaloneWindow
 * @short_description: Window for displaying standalone spokes
 *
 * A #AnacondaStandaloneWindow is a top-level window that displays a standalone
 * spoke.  A standalone spoke is like a normal spoke, but is not entered via a
 * hub.  Instead, it is displayed by itself.  Examples include the welcome and
 * network configuration screens at the beginning of installation.
 *
 * The window consist of three areas:
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

enum {
    SIGNAL_QUIT_CLICKED,
    SIGNAL_CONTINUE_CLICKED,
    LAST_SIGNAL
};

#define QUIT_TEXT       N_("_Quit")
#define CONTINUE_TEXT   N_("_Continue")

static guint window_signals[LAST_SIGNAL] = { 0 };

struct _AnacondaStandaloneWindowPrivate {
    GtkWidget  *button_box;
    GtkWidget  *continue_button, *quit_button;
};

static void anaconda_standalone_window_quit_clicked(GtkButton *button,
                                                    AnacondaStandaloneWindow *win);
static void anaconda_standalone_window_continue_clicked(GtkButton *button,
                                                        AnacondaStandaloneWindow *win);
static void anaconda_standalone_window_realize(GtkWidget *widget,
                                               AnacondaStandaloneWindow *win);

G_DEFINE_TYPE(AnacondaStandaloneWindow, anaconda_standalone_window, ANACONDA_TYPE_BASE_WINDOW)

static void anaconda_standalone_window_class_init(AnacondaStandaloneWindowClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);

    klass->quit_clicked = NULL;
    klass->continue_clicked = NULL;

    /**
     * AnacondaStandaloneWindow::quit-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the quit button has been activated (pressed and released).
     *
     * Since: 1.0
     */
    window_signals[SIGNAL_QUIT_CLICKED] = g_signal_new("quit-clicked",
                                                       G_TYPE_FROM_CLASS(object_class),
                                                       G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                       G_STRUCT_OFFSET(AnacondaStandaloneWindowClass, quit_clicked),
                                                       NULL, NULL,
                                                       g_cclosure_marshal_VOID__VOID,
                                                       G_TYPE_NONE, 0);

    /**
     * AnacondaStandaloneWindow::continue-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the continue button has been activated (pressed and released).
     *
     * Since: 1.0
     */
    window_signals[SIGNAL_CONTINUE_CLICKED] = g_signal_new("continue-clicked",
                                                           G_TYPE_FROM_CLASS(object_class),
                                                           G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                           G_STRUCT_OFFSET(AnacondaStandaloneWindowClass, continue_clicked),
                                                           NULL, NULL,
                                                           g_cclosure_marshal_VOID__VOID,
                                                           G_TYPE_NONE, 0);

    g_type_class_add_private(object_class, sizeof(AnacondaStandaloneWindowPrivate));
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
    GtkWidget *main_box = anaconda_base_window_get_main_box(ANACONDA_BASE_WINDOW(win));

    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_STANDALONE_WINDOW,
                                            AnacondaStandaloneWindowPrivate);

    /* Create the buttons. */
    win->priv->quit_button = gtk_button_new_with_mnemonic(_(QUIT_TEXT));
    win->priv->continue_button = gtk_button_new_with_mnemonic(_(CONTINUE_TEXT));

    /* Hook up some signals for those buttons.  The signal handlers here will
     * just raise our own custom signals for the whole window.
     */
    g_signal_connect(win->priv->quit_button, "clicked",
                     G_CALLBACK(anaconda_standalone_window_quit_clicked), win);
    g_signal_connect(win->priv->continue_button, "clicked",
                     G_CALLBACK(anaconda_standalone_window_continue_clicked), win);

    /* Create the button box and pack the buttons into it. */
    win->priv->button_box = gtk_button_box_new(GTK_ORIENTATION_HORIZONTAL);
    gtk_widget_set_margin_left(win->priv->button_box, 6);
    gtk_widget_set_margin_right(win->priv->button_box, 6);
    gtk_widget_set_margin_bottom(win->priv->button_box, 6);
    gtk_button_box_set_layout(GTK_BUTTON_BOX(win->priv->button_box), GTK_BUTTONBOX_EDGE);
    gtk_container_add(GTK_CONTAINER(win->priv->button_box), win->priv->quit_button);
    gtk_container_add(GTK_CONTAINER(win->priv->button_box), win->priv->continue_button);

    gtk_box_pack_start(GTK_BOX(main_box), win->priv->button_box, FALSE, TRUE, 0);

    /* It would be handy for F12 to continue to work like it did in the old
     * UI, by skipping you to the next screen.
     */
    g_signal_connect(win, "realize", G_CALLBACK(anaconda_standalone_window_realize), win);
}

static void anaconda_standalone_window_realize(GtkWidget *widget,
                                               AnacondaStandaloneWindow *win) {
    GtkAccelGroup *accel_group = gtk_accel_group_new();
    gtk_window_add_accel_group(GTK_WINDOW(win), accel_group);
    gtk_widget_add_accelerator(win->priv->continue_button,
                               "clicked",
                               accel_group,
                               GDK_KEY_F12,
                               0,
                               0);
}

static void anaconda_standalone_window_quit_clicked(GtkButton *button,
                                                    AnacondaStandaloneWindow *win) {
    g_signal_emit(win, window_signals[SIGNAL_QUIT_CLICKED], 0);
}

static void anaconda_standalone_window_continue_clicked(GtkButton *button,
                                                        AnacondaStandaloneWindow *win) {
    g_signal_emit(win, window_signals[SIGNAL_CONTINUE_CLICKED], 0);
}

/**
 * anaconda_standalone_window_get_may_continue:
 * @win: a #AnacondaStandaloneWindow
 *
 * Returns whether or not the continue button is sensitive (thus, whether the
 * user may continue forward from this window).
 *
 * Returns: Whether the continue button on @win is sensitive.
 *
 * Since: 1.0
 */
gboolean anaconda_standalone_window_get_may_continue(AnacondaStandaloneWindow *win) {
    return gtk_widget_get_sensitive(win->priv->continue_button);
}

/**
 * anaconda_standalone_window_set_may_continue:
 * @win: a #AnacondaStandaloneWindow
 * @may_continue: %TRUE if this window's continue button should be sensitive.
 *
 * Specifies whether the user may continue forward from this window.  If so,
 * the continue button will be made sensitive.  Windows default to continuable
 * so you must set it as false if you want.  The reason the user may not be
 * able to continue is if there is required information the user must enter
 * when no reasonable default may be given.
 *
 * Since: 1.0
 */
void anaconda_standalone_window_set_may_continue(AnacondaStandaloneWindow *win,
                                                 gboolean may_continue) {
    gtk_widget_set_sensitive(win->priv->continue_button, may_continue);
}

/**
 * anaconda_standalone_window_retranslate:
 * @win: a #AnacondaStaldaloneWindow
 * @lang: target language
 *
 * Reload translations for this widget as needed.  Generally, this is not
 * needed.  However when changing the language during installation, we need
 * to be able to make sure the screen gets retranslated.  This function is
 * kind of ugly but avoids having to destroy and reload the screen.
 *
 * Since: 1.0
 */
void anaconda_standalone_window_retranslate(AnacondaStandaloneWindow *win, const char *lang) {
    anaconda_base_window_retranslate(ANACONDA_BASE_WINDOW(win), lang);
    gtk_button_set_label(GTK_BUTTON(win->priv->quit_button), _(QUIT_TEXT));
    gtk_button_set_label(GTK_BUTTON(win->priv->continue_button), _(CONTINUE_TEXT));
}
