/*
 * mini-wm.c - simple keyboard focus handling 'wm'.
 *
 * Copyright (C) 2002  Red Hat, Inc.  All rights reserved.
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
 * Author(s): Owen Taylor <otaylor@redhat.com>
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <gdk/gdkx.h>
#include <gtk/gtk.h>
#include <X11/extensions/Xcomposite.h>

static gboolean
is_focusable (Window window)
{
  Display *xdisplay = GDK_DISPLAY ();
  XWindowAttributes xwa;
  gboolean result = FALSE;

  gdk_error_trap_push ();
  if (XGetWindowAttributes (xdisplay, window, &xwa))
    {
      if (!xwa.override_redirect && xwa.map_state == IsViewable)
	result = TRUE;
    }
  gdk_error_trap_pop ();

  return result;
}

static void
check_focus ()
{
  Window *children;
  unsigned int n_children;
  Window root;
  Window parent;
  
  XQueryTree (GDK_DISPLAY(), GDK_ROOT_WINDOW(),
	      &root, &parent, &children, &n_children);

  while (n_children > 0) {
      if (is_focusable (children[n_children-1])) {
	  gdk_error_trap_push ();
	  XSetInputFocus (GDK_DISPLAY(), children[n_children-1], 
			  RevertToPointerRoot, CurrentTime);
	  XSync (GDK_DISPLAY(), 0);
	  if (gdk_error_trap_pop () == 0)
	    break;
      }
      n_children--;
  }

  XFree (children);
}

GdkFilterReturn
mini_wm_root_filter (GdkXEvent *xevent,
		     GdkEvent *event,
		     gpointer  data)
{
  XEvent *xev = xevent;

  if (xev->xany.type == MapNotify ||
      xev->xany.type == UnmapNotify ||
      xev->xany.type == ConfigureNotify ||
      xev->xany.type == DestroyNotify)
    {
      check_focus ();
    }
    
  return GDK_FILTER_CONTINUE;
}

void
mini_wm_start (void)
{
  XWindowAttributes attrs;

  XCompositeRedirectSubwindows (GDK_DISPLAY(), GDK_ROOT_WINDOW(),
				CompositeRedirectAutomatic);

  XGetWindowAttributes (GDK_DISPLAY(), GDK_ROOT_WINDOW(), &attrs);
  XSelectInput (GDK_DISPLAY(), GDK_ROOT_WINDOW(),
		attrs.your_event_mask | SubstructureNotifyMask);

  gdk_window_add_filter (GDK_ROOT_PARENT (), mini_wm_root_filter, NULL);

  check_focus ();
}

int main( int   argc,
          char *argv[] )
{
    gtk_init (&argc, &argv);

    mini_wm_start ();

    /* Indicate back to anaconda that we now have established
     * connection to the display. */
    if (write(1, "#", 1) == -1) abort();

    gtk_main();

    return(0);
}
