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

#ifndef ANACONDA_SPINNER_H
#define ANACONDA_SPINNER_H

#include <gtk/gtk.h>

#define ANACONDA_TYPE_SPINNER           (anaconda_spinner_get_type ())
#define ANACONDA_SPINNER(o)             (G_TYPE_CHECK_INSTANCE_CAST ((o), ANACONDA_TYPE_SPINNER, AnacondaSpinner))
#define ANACONDA_SPINNER_CLASS(k)       (G_TYPE_CHECK_CLASS_CAST((k), ANACONDA_TYPE_SPINNER, AnacondaSpinnerClass))
#define ANACONDA_IS_SPINNER(o)          (G_TYPE_CHECK_INSTANCE_TYPE ((o), ANACONDA_TYPE_SPINNER))
#define ANACONDA_IS_SPINNER_CLASS(k)    (G_TYPE_CHECK_CLASS_TYPE ((k), ANACONDA_TYPE_SPINNER))
#define ANACONDA_SPINNER_GET_CLASS(o)   (G_TYPE_INSTANCE_GET_CLASS ((o), ANACONDA_TYPE_SPINNER, AnacondaSpinnerClass))

G_BEGIN_DECLS

typedef struct _AnacondaSpinner         AnacondaSpinner;
typedef struct _AnacondaSpinnerClass    AnacondaSpinnerClass;
typedef struct _AnacondaSpinnerPrivate  AnacondaSpinnerPrivate;

struct _AnacondaSpinner
{
    GtkImage parent;

    /*< private >*/
    AnacondaSpinnerPrivate *priv;
};

struct _AnacondaSpinnerClass
{
    GtkImageClass parent_class;
};

GType           anaconda_spinner_get_type       (void);

GtkWidget *     anaconda_spinner_new            (void);
gboolean        anaconda_spinner_get_active     (AnacondaSpinner *spinner);
void            anaconda_spinner_set_active     (AnacondaSpinner *spinner, gboolean active);
void            anaconda_spinner_start          (AnacondaSpinner *spinner);
void            anaconda_spinner_stop           (AnacondaSpinner *spinner);

G_END_DECLS

#endif /* E_SPINNER_H */
