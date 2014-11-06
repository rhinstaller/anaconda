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

#include "config.h"

#include "BaseWindow.h"
#include "BaseStandalone.h"
#include "intl.h"

/**
 * SECTION: BaseStandalone
 * @title: AnacondaBaseStandalone
 * @short_description: Abstract base class for standalone Anaconda windows.
 *
 * #AnacondaBaseStandalone is an abstract base class for standalone windows
 * in Anaconda; i.e., windows that do not appear in or depend upon a hub.
 * A #AnacondaBaseStandalone can continue to the next #AnacondaBaseStandalone
 * or quit the installer.
 *
 * Since: 3.0
 */

/* change value below to make sidebar bigger / smaller */
#define STANDALONE_SIDEBAR_WIDTH_PCT    (0.15)

enum {
    SIGNAL_QUIT_CLICKED,
    SIGNAL_CONTINUE_CLICKED,
    LAST_SIGNAL
};

static guint standalone_signals[LAST_SIGNAL] = { 0 };

enum {
    PROP_QUIT_BUTTON = 1,
    PROP_CONTINUE_BUTTON
};

struct _AnacondaBaseStandalonePrivate {
    GtkWidget *quit_button, *continue_button;
    gulong quit_clicked_handler_id, continue_clicked_handler_id;
};

static void anaconda_base_standalone_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);
static void anaconda_base_standalone_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void anaconda_base_standalone_size_allocate(GtkWidget *window, GtkAllocation *allocation);
static gboolean anaconda_base_standalone_on_draw(GtkWidget *window, cairo_t *cr);
static void anaconda_base_standalone_dispose(GObject *object);
static void anaconda_base_standalone_set_quit_button(AnacondaBaseStandalone *win, GtkButton *button);
static void anaconda_base_standalone_set_continue_button(AnacondaBaseStandalone *win, GtkButton *button);
static void anaconda_base_standalone_quit_clicked(GtkButton *button, gpointer user_data);
static void anaconda_base_standalone_continue_clicked(GtkButton *button, gpointer user_data);

G_DEFINE_ABSTRACT_TYPE(AnacondaBaseStandalone, anaconda_base_standalone, ANACONDA_TYPE_BASE_WINDOW)

static void anaconda_base_standalone_class_init(AnacondaBaseStandaloneClass *klass) {
    GObjectClass *object_class = G_OBJECT_CLASS(klass);
    GtkWidgetClass *widget_class = GTK_WIDGET_CLASS(klass);

    object_class->set_property = anaconda_base_standalone_set_property;
    object_class->get_property = anaconda_base_standalone_get_property;
    object_class->dispose = anaconda_base_standalone_dispose;

    widget_class->draw = anaconda_base_standalone_on_draw;
    widget_class->size_allocate = anaconda_base_standalone_size_allocate;

    /**
     * AnacondaBaseStandalone::quit-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the quit button has been activated (pressed and released).
     *
     * Since: 3.0
     */
    standalone_signals[SIGNAL_QUIT_CLICKED] = g_signal_new("quit-clicked",
                                                           G_TYPE_FROM_CLASS(object_class),
                                                           G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                           G_STRUCT_OFFSET(AnacondaBaseStandaloneClass, quit_clicked),
                                                           NULL, NULL,
                                                           g_cclosure_marshal_VOID__VOID,
                                                           G_TYPE_NONE, 0);

    /**
     * AnacondaBaseStandalone::continue-clicked:
     * @window: the window that received the signal
     *
     * Emitted when the continue button has been activated (pressed and released).
     *
     * Since: 3.0
     */
    standalone_signals[SIGNAL_CONTINUE_CLICKED] = g_signal_new("continue-clicked",
                                                               G_TYPE_FROM_CLASS(object_class),
                                                               G_SIGNAL_RUN_FIRST | G_SIGNAL_ACTION,
                                                               G_STRUCT_OFFSET(AnacondaBaseStandaloneClass, continue_clicked),
                                                               NULL, NULL,
                                                               g_cclosure_marshal_VOID__VOID,
                                                               G_TYPE_NONE, 0);

    /*
     * These two properties can't be CONSTRUCT_ONLY, since GtkBuilder will normally
     * set them after construction. For a window that sets its quit-button or continue-button
     * property to a GtkButton defined as a child of the window, Builder will construct
     * the window, then construct the Button and set the property on the window.
     */

    /**
     * AnacondaBaseStandalone::quit-button:
     *
     * The button to quit anaconda.
     *
     * Since: 3.0
     */
    g_object_class_install_property(object_class,
                                    PROP_QUIT_BUTTON,
                                    g_param_spec_object("quit-button",
                                                        P_("Quit button"),
                                                        P_("The button to quit Anaconda"),
                                                        GTK_TYPE_BUTTON,
                                                        G_PARAM_READWRITE | G_PARAM_CONSTRUCT));

    /**
     * AnacondaBaseStandalone::continue-button:
     *
     * The button to continue to the next window.
     *
     * Since: 3.0
     */
    g_object_class_install_property(object_class,
                                    PROP_CONTINUE_BUTTON,
                                    g_param_spec_object("continue-button",
                                                        P_("Continue button"),
                                                        P_("The button to continue to the next window"),
                                                        GTK_TYPE_BUTTON,
                                                        G_PARAM_READWRITE | G_PARAM_CONSTRUCT));

    g_type_class_add_private(object_class, sizeof(AnacondaBaseStandalonePrivate));
}

static void anaconda_base_standalone_init(AnacondaBaseStandalone *win) {
    win->priv = G_TYPE_INSTANCE_GET_PRIVATE(win,
                                            ANACONDA_TYPE_BASE_STANDALONE,
                                            AnacondaBaseStandalonePrivate);
}

static void anaconda_base_standalone_get_property(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) {
    AnacondaBaseStandalone *win = ANACONDA_BASE_STANDALONE(object);
    AnacondaBaseStandalonePrivate *priv = win->priv;

    switch (prop_id) {
        case PROP_QUIT_BUTTON:
            g_value_set_object(value, priv->quit_button);
            break;
        case PROP_CONTINUE_BUTTON:
            g_value_set_object(value, priv->continue_button);
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

static void anaconda_base_standalone_set_property(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) {
    AnacondaBaseStandalone *win = ANACONDA_BASE_STANDALONE(object);

    switch (prop_id) {
        case PROP_QUIT_BUTTON:
            anaconda_base_standalone_set_quit_button(win, g_value_get_object(value));
            break;
        case PROP_CONTINUE_BUTTON:
            anaconda_base_standalone_set_continue_button(win, g_value_get_object(value));
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

static int get_sidebar_width(GtkWidget *window) {
    GtkAllocation allocation;

    gtk_widget_get_allocation(window, &allocation);
    return allocation.width * STANDALONE_SIDEBAR_WIDTH_PCT;
}

static int get_sidebar_height(GtkWidget *window) {
    GtkAllocation allocation;
    gtk_widget_get_allocation(window, &allocation);
    return allocation.height;
}

/* Move base window content appropriate amount of space to make room for sidebar */
static void anaconda_base_standalone_size_allocate(GtkWidget *window, GtkAllocation *allocation) {
    GtkAllocation child_allocation;
    GtkWidget *child;
    int sidebar_width;

    GTK_WIDGET_CLASS(anaconda_base_standalone_parent_class)->size_allocate(window, allocation);

    /*
     * For RTL languages, the width is reduced by the same amount, but the
     * start of the window does not need to move.
     */
    gtk_widget_set_allocation(window, allocation);
    sidebar_width = get_sidebar_width(window);
    child_allocation.y = allocation->y;
    child_allocation.width = allocation->width-sidebar_width;
    child_allocation.height = allocation->height;

    if (gtk_get_locale_direction() == GTK_TEXT_DIR_LTR)
        child_allocation.x = allocation->x+sidebar_width;
    else
        child_allocation.x = allocation->x;

    child = gtk_bin_get_child (GTK_BIN (window));
    if (child && gtk_widget_get_visible (child))
        gtk_widget_size_allocate (child, &child_allocation);
}

/* function to override default drawing to insert sidebar image */
static gboolean anaconda_base_standalone_on_draw(GtkWidget *win, cairo_t *cr) {
    GtkStyleContext *context;
    gdouble sidebar_x;
    gdouble sidebar_width;

    /* calls parent class' draw handler */
    GTK_WIDGET_CLASS(anaconda_base_standalone_parent_class)->draw(win,cr);

    sidebar_width = get_sidebar_width(win);

    /* For RTL languages, move the sidebar to the right edge */
    if (gtk_get_locale_direction() == GTK_TEXT_DIR_LTR) {
        sidebar_x = 0;
    } else {
        GtkAllocation allocation;
        gtk_widget_get_allocation(win, &allocation);
        sidebar_x = allocation.width - sidebar_width;
    }

    context = gtk_widget_get_style_context(win);
    gtk_style_context_save (context);

    gtk_style_context_add_class(context, "logo-sidebar");
    gtk_render_background(context, cr, sidebar_x, 0, sidebar_width, get_sidebar_height(win));
    gtk_style_context_remove_class(context, "logo-sidebar");

    gtk_style_context_add_class(context, "logo");
    gtk_render_background(context, cr, sidebar_x, 0, sidebar_width, get_sidebar_height(win));
    gtk_style_context_remove_class(context, "logo");

    gtk_style_context_add_class(context, "product-logo");
    gtk_render_background(context, cr, sidebar_x, 0, sidebar_width, get_sidebar_height(win));
    gtk_style_context_remove_class(context, "product-logo");

    gtk_style_context_restore (context);

    return TRUE; /* TRUE to avoid default draw handler */
}

static void anaconda_base_standalone_dispose(GObject *object) {
    AnacondaBaseStandalone *win = ANACONDA_BASE_STANDALONE(object);

    anaconda_base_standalone_set_quit_button(win, NULL);
    anaconda_base_standalone_set_continue_button(win, NULL);

    G_OBJECT_CLASS(anaconda_base_standalone_parent_class)->dispose(object);
}

static void anaconda_base_standalone_set_quit_button(AnacondaBaseStandalone *win, GtkButton *button) {
    AnacondaBaseStandalonePrivate *priv = win->priv;

    if (priv->quit_button) {
        g_signal_handler_disconnect(priv->quit_button, priv->quit_clicked_handler_id);
        g_object_unref(priv->quit_button);
    }

    priv->quit_button = GTK_WIDGET(button);

    if (priv->quit_button) {
        g_object_ref(priv->quit_button);
        priv->quit_clicked_handler_id = g_signal_connect(priv->quit_button, "clicked", G_CALLBACK(anaconda_base_standalone_quit_clicked), win);
    }
}

static void anaconda_base_standalone_set_continue_button(AnacondaBaseStandalone *win, GtkButton *button) {
    AnacondaBaseStandalonePrivate *priv = win->priv;

    if (priv->continue_button) {
        g_signal_handler_disconnect(priv->continue_button, priv->continue_clicked_handler_id);
        g_object_unref(priv->continue_button);
    }

    priv->continue_button = GTK_WIDGET(button);

    if (priv->continue_button) {
        g_object_ref(priv->continue_button);
        priv->continue_clicked_handler_id = g_signal_connect(priv->continue_button, "clicked", G_CALLBACK(anaconda_base_standalone_continue_clicked), win);
    }
}

static void anaconda_base_standalone_quit_clicked(GtkButton *button, gpointer user_data) {
    g_signal_emit(user_data, standalone_signals[SIGNAL_QUIT_CLICKED], 0);
}

static void anaconda_base_standalone_continue_clicked(GtkButton *button, gpointer user_data) {
    g_signal_emit(user_data, standalone_signals[SIGNAL_CONTINUE_CLICKED], 0);
}

/**
 * anaconda_base_standalone_get_may_continue:
 * @win: a #AnacondaBaseStandalone
 *
 * Returns: Whether or not the continue button is sensitive (thus, whether the
 * user may continue forward from this window).
 *
 * Since: 3.0
 */
gboolean anaconda_base_standalone_get_may_continue(AnacondaBaseStandalone *win) {
    if (win->priv->continue_button) {
        return gtk_widget_get_sensitive(win->priv->continue_button);
    }
    return FALSE;
}

/**
 * anaconda_base_standalone_set_may_continue:
 * @win: a #AnacondaBaseStandalone
 * @may_continue: %TRUE if this window's continue buttons should be sensitive
 *
 * Specifies whether the user may continue forward from this window.  If so,
 * the continue button will be made sensitive.  Windows default to continuable
 * so you must set it as false if you want.  The reason the user may not be
 * able to continue is if there is required information the user must enter
 * when no reasonable default may be given.
 *
 * Since: 3.0
 */
void anaconda_base_standalone_set_may_continue(AnacondaBaseStandalone *win, gboolean may_continue) {
    if (win->priv->continue_button) {
        gtk_widget_set_sensitive(win->priv->continue_button, may_continue);
    }
}

/**
 * anaconda_base_standalone_get_quit_button:
 * @win: a #AnacondaBaseStandalone
 *
 * Returns: (transfer none): the quit button
 *
 * Since: 3.0
 */
GtkButton * anaconda_base_standalone_get_quit_button(AnacondaBaseStandalone *win) {
    return GTK_BUTTON(win->priv->quit_button);
}

/**
 * anaconda_base_standalone_get_continue_button:
 * @win: a #AnacondaBaseStandalone
 *
 * Returns: (transfer none): the continue button
 *
 * Since: 3.0
 */
GtkButton * anaconda_base_standalone_get_continue_button(AnacondaBaseStandalone *win) {
    return GTK_BUTTON(win->priv->continue_button);
}
