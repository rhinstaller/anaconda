/*
 * mini-wm.c - simple keyboard focus handling 'wm'.
 *
 * Owen Taylor <otaylor@redhat.com>
 *
 * Copyright 2002 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */


#include <stdio.h>

#include <gdk/gdkx.h>
#include <gdk/gdkx.h>

static void
check_focus ()
{
  Window *children;
  unsigned int n_children;
  Window root;
  Window parent;
  
  XQueryTree (GDK_DISPLAY(), GDK_ROOT_WINDOW(),
	      &root, &parent, &children, &n_children);

  if (n_children > 0) {
      gdk_error_trap_push ();
      XSetInputFocus (GDK_DISPLAY(), children[n_children-1], 
		      RevertToPointerRoot, CurrentTime);
      XSync (GDK_DISPLAY(), 0);
      if (gdk_error_trap_pop () != 0)
	  printf("Failed on XSetInputFocus()");
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
      xev->xany.type == ConfigureNotify)
    check_focus ();
    
  return GDK_FILTER_CONTINUE;
}

void
mini_wm_start (void)
{
  XWindowAttributes attrs;

  XGetWindowAttributes (GDK_DISPLAY(), GDK_ROOT_WINDOW(), &attrs);
  XSelectInput (GDK_DISPLAY(), GDK_ROOT_WINDOW(),
		attrs.your_event_mask | SubstructureNotifyMask);

  gdk_window_add_filter (GDK_ROOT_PARENT (), mini_wm_root_filter, NULL);
}

int main( int   argc,
          char *argv[] )
{

    gtk_init (&argc, &argv);

    mini_wm_start ();

    gtk_main();

    return(0);
}
