/* Copyright (C) 1999 Red Hat, Inc. */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#include <gnome.h>
#include <stdlib.h>
#include <unistd.h>
#include <math.h>

#include "gnome-map.h"
#include "gnome-canvas-dot.h"
#include "timezones.h"

/* Command line options */
/* image     - filename of file to use for map (must be PNG for antialias) */
/* mapwidth  - width to scale image to (also size of canvas widget)        */
/* mapheight - height to scale image to (also size of canvas widget)       */
/* aa        - if TRUE use antialiased canvas instead of normal            */
static gchar *image = NULL;
static int mapwidth = -1;
static int mapheight = -1;
static int aa=FALSE;

static const struct poptOption options[] = {
    {"image", '\0', POPT_ARG_STRING, &image, 0, N_("Map Image to display"), NULL},
    {"width", '\0', POPT_ARG_INT, &mapwidth, 0, N_("Width of map (in pixels)"), NULL},
    {"antialias", '\0', POPT_ARG_INT, &aa, 0, N_("Enable antialias"), NULL},
    { NULL, '\0', 0, NULL, 0}
};


/* time zone data */
/* This is an array of TimeZoneLocations (see timezone.h). Created */
/* by a call to loadTZDB                                           */
GPtrArray      *Locations=NULL;

/* index in all Locations GPtrArray of currently selected city */
gint            curselection=-1;

/* toplevel app window */
GtkWidget *mainwindow;

/* other widgets for the top-level GUI */
GtkWidget *statusbar;

/* locationlist is the clist on the right side of the GUI showing all the */
/* currently viewable locations.                                          */
/* It is created and updated by the create_location_list () function      */
GtkWidget *locationlist;

/* if TRUE we do not want to act on the select_row events to locationlist */
/* used when we are manually manipulating rows in locationlist and we     */
/* want to ignore the events going to the callback.                       */
gboolean ignore_locationlist_selectevents=FALSE;

/* Canvas item circle for selected location */
GnomeCanvasItem *selmarker=NULL;
double          oldselx, oldsely; /* old location of selection */
#define SELECTED_COLOR "red"

/* Canvas item circle for hilited location and optionally rubberband */
/* line pointing from cursor to hilited location                     */
GnomeCanvasItem *hilitemarker=NULL;
GnomeCanvasItem *hiliterubberband=NULL;
gint            hiliteindex=-1;         /* index in markers array of */
                                        /* currently hilted location */
double          oldhilitex, oldhilitey; /* old location of hilite circle */
#define HILITED_COLOR   "limegreen"

/* set to appropriate value to enable/disable the rubberband */
#define USE_HILITE_RUBBERBAND TRUE

/* color for normal (non-hilited or -selected locations */
#define CITY_COLOR     "yellow"

/* map and city structures */
/* See gnome-map.h for more info on the GnomeMap structure */
/* markers is an array of pointers to GnomeCanvasItems which are the */
/* indicators for the locations in the Locations array */
GnomeMap *WorldMap;
GnomeCanvasItem **markers=NULL;

/* view data */
/* Views are defined by a range of either longitude or latitude     */
/* as well as the central value for the other axis.                 */
typedef enum
{
    LONGITUDE_CONSTRAINT,
    LATITUDE_CONSTRAINT
} ViewContraintType;

struct _VIEW_DEF {
    gchar    *name;
    ViewContraintType type;
    double   constraint1, constraint2, constraint3;
};

typedef struct _VIEW_DEF ViewDefinition;

ViewDefinition Views[] = {
    { N_("World"),         LONGITUDE_CONSTRAINT, -180.0, 180.0, 0.0 },
    { N_("North America"), LONGITUDE_CONSTRAINT, -171.0, -21.0, 40.0 },
    { N_("South America"), LATITUDE_CONSTRAINT,   15.0,   -70.0, -70.0 },
    { N_("Pacific Rim"),   LATITUDE_CONSTRAINT,    -47.0, 47.0, 155.0},
    { N_("Europe"),        LONGITUDE_CONSTRAINT,  -25.0, 70.0, 45.0 },
    { N_("Africa"),        LATITUDE_CONSTRAINT,   40.0,   -40.0, 15.0},
    { N_("Asia"),          LONGITUDE_CONSTRAINT,  20.0, 165.0, 40.0}
};

gint numviews = sizeof(Views)/sizeof(ViewDefinition);


static gint item_event (GnomeCanvasItem *item, GdkEvent *event, gpointer data);
static GtkWidget *create_location_list ( GtkWidget **returnlist );

/* give a location name search for match in Locations db */
/* returns index if found, -1 if not                     */
static int
find_location (gchar *locname)
{
    TimeZoneLocation  *loc;
    gint i;

    for (i=0; i < Locations->len; i++) {
	loc = g_ptr_array_index (Locations, i);

	if (!strcmp (loc->zone, locname))
	    return i;
    }

    return -1;
}


/* find nearest location to specified map coords - clips to current view */
/* if no match return -1                                                 */
static int
find_nearest ( double longitude, double latitude )
{
    double mindist = 0;
    double dist;
    double dx, dy;
    int    i, mini;
    gboolean first=TRUE;
    TimeZoneLocation  *loc;

    mini = -1;
    for (i=0; i < Locations->len; i++) {
	loc = g_ptr_array_index (Locations, i);

	if (!gnome_map_is_loc_in_view (WorldMap, 
				       loc->longitude, loc->latitude))
	    continue;

	dx = (loc->longitude-longitude);
	dy = (loc->latitude-latitude);
	dist = dx*dx + dy*dy;

	if (dist < mindist || first) {
	    mindist = dist;
	    mini = i;
	    first = FALSE;
	}
    }

    return mini;
}

/* attach to signal for canvas items so we can track motion and mouse */
/* events                                                             */
static void
setup_item (GnomeCanvasItem *item)
{
    gtk_signal_connect (GTK_OBJECT (item), "event",
			(GtkSignalFunc) item_event,
			NULL);
}

/* Moves marker (a circle currently) to the specified location */
/* and sets it to the specified color.  The oldx and oldy      */
/* variables are required because the canvas only allows one   */
/* to do relative moves for items.  These are automatically    */
/* set to x and y by this function before it returns.          */
/*                                                             */
/* The first time this function is called for a given marker   */
/* *curmarker should equal NULL.  The marker will be created   */
/* automatically.                                              */

static void
set_flag_marker (GnomeCanvasItem **curmarker, gchar *color,
		 double x, double y, double *oldx, double *oldy)
{
    GnomeCanvasGroup  *canvas_root;
    GnomeCanvasItem   *group;

    g_return_if_fail ( color != NULL );

    canvas_root = gnome_canvas_root (GNOME_CANVAS(WorldMap->canvas));
    if (!*curmarker) {

	group = gnome_canvas_item_new ( canvas_root,
					gnome_canvas_group_get_type(),
					"x", x,
					"y", y,
					NULL);
	
#define MARKER_RADIUS 3.5
#define MARKER_WIDTH_PIX 1

        setup_item (gnome_canvas_item_new (GNOME_CANVAS_GROUP (group),
					   gnome_canvas_text_get_type (),
					   "font", "-adobe-helvetica-bold-r-normal--12-*-72-72-p-*-iso8859-1",
					   "anchor", GTK_ANCHOR_CENTER,
					   "fill_color", "red",
					   "text", "X",
					   NULL));

  	*curmarker = GNOME_CANVAS_ITEM (group); 
    } else {
	gnome_canvas_item_move ( *curmarker, x - *oldx, y - *oldy );
    }

    *oldx = x;
    *oldy = y;
}

/* Given a pointer to a GnomeMap and an index into the Locations db */
/* mark it as the selected location on the canvas                   */
static void
map_mark_location_selected (GnomeMap *map, gint index)
{
    TimeZoneLocation *loc;
    double selx, sely;

    g_return_if_fail ( map != NULL );
    g_return_if_fail ( index >= 0 );

    loc = g_ptr_array_index (Locations, index);
    
    gnome_map_xlat_map2screen ( map, 
				loc->longitude,	loc->latitude,
				&selx, &sely );
    set_flag_marker (&selmarker, SELECTED_COLOR,
		     selx, sely, &oldselx, &oldsely);
    
    if (curselection >= 0) {
	gnome_canvas_item_set (markers[curselection],
			       "fill_color", CITY_COLOR, NULL);
	gnome_canvas_item_show (markers[curselection]);
    }
/*      gnome_canvas_item_set (markers[index], "fill_color",  */
/*  			   SELECTED_COLOR, NULL); */
    gnome_canvas_item_hide (markers[index]);
    gnome_canvas_item_raise_to_top (selmarker);
}

/* Given a pointer to a GnomeMap and an index into the Locations db */
/* mark it as the selected location in the clist of locations       */
/* The jumpto gboolean is used to specify if the clist should be    */
/* forced to scroll to the new location.  Used because when the     */
/* clist is autoscrolling we do not want to force selection to be   */
/* constantly recentered.                                           */
static void
list_mark_location_selected (GnomeMap *map, gint index, gboolean jumpto)
{
    gint newrow;

    /* We're messing with list manually, so let callback know to */
    /* ignore any events till we're done                         */
    ignore_locationlist_selectevents = TRUE;

    /* if current selection is visible then select it again, otherwise */
    /* change clist to not have a current selection                    */
    if (index >= 0) {
	TimeZoneLocation *loc = g_ptr_array_index (Locations, index);
	
	if (gnome_map_is_loc_in_view (map,loc->longitude,loc->latitude)) {
	    gtk_clist_set_selection_mode (GTK_CLIST (locationlist), 
					  GTK_SELECTION_BROWSE);
	} else {
	    gtk_clist_set_selection_mode (GTK_CLIST (locationlist), 
					  GTK_SELECTION_SINGLE);
	}
    }

    /* find in list of locations and set as current */
    newrow = gtk_clist_find_row_from_data( GTK_CLIST (locationlist),
					   GINT_TO_POINTER (index));

    if (newrow >= 0 ) {
	gtk_clist_select_row (GTK_CLIST(locationlist), newrow, 0);
	if (jumpto && gtk_clist_row_is_visible (GTK_CLIST (locationlist), newrow) != GTK_VISIBILITY_FULL) {
	    gtk_clist_moveto (GTK_CLIST (locationlist), newrow , 0, 0.5, 0.5 );
	}
    }

    /* We're done mucking with clist, ok to listen to events again */
    ignore_locationlist_selectevents = FALSE;

}
/* handles all canvas drawing for making the selected location # index */
/* in the sorted list in the Locations variable                        */
static void
set_selection (gint index, gboolean jumpto)
{
    g_return_if_fail ( index >= 0 );

    map_mark_location_selected (WorldMap, index);

    list_mark_location_selected (WorldMap, index, jumpto);

    /* NOTE: curselection is global variable. Only place it gets set */
    curselection = index;
}

/* Given an index into the Locations db and a position, draw the hilite */
/* marker around it to indicate it is city cursor is pointing at        */
static void
set_hilited (gint index, double item_x, double item_y)
{
    TimeZoneLocation *loc;
    GnomeCanvasPoints *points;

    g_return_if_fail ( index >= 0 );

    loc = g_ptr_array_index (Locations, index);

    points = gnome_canvas_points_new (2);
    points->coords[0] = item_x;
    points->coords[1] = item_y;
    gnome_map_xlat_map2screen ( WorldMap,
				loc->longitude, loc->latitude,
				&points->coords[2], &points->coords[3] );
    if (hiliterubberband) {
	gnome_canvas_item_set (hiliterubberband, "points", points, NULL);
	gnome_canvas_item_show (hiliterubberband);
    } else {
	GnomeCanvasGroup *canvas_root = gnome_canvas_root (GNOME_CANVAS (WorldMap->canvas));
	
	hiliterubberband = gnome_canvas_item_new (canvas_root,
					  gnome_canvas_line_get_type (),
					  "points", points,
					  "fill_color", HILITED_COLOR,
					  "width_pixels", 2,
					  "first_arrowhead", FALSE,
					  "last_arrowhead", TRUE,
					  "arrow_shape_a", 4.0,
					  "arrow_shape_b", 8.0,
					  "arrow_shape_c", 4.0,
					  NULL);
	setup_item (hiliterubberband);
    }

    /* Set USE_HILITE_RUBBER band define at top of file for desired */
    /* behavior                                                     */
    if (!USE_HILITE_RUBBERBAND)
	gnome_canvas_item_hide (hiliterubberband);

    /* if hilited city isn't also currently selected city, draw the */
    /* hilite marker as well                                        */
    if (index != curselection) {
	/*
	set_flag_marker ( &hilitemarker, HILITED_COLOR,
			  points->coords[2], points->coords[3],
			  &oldhilitex, &oldhilitey );
	*/
	
/*  	gnome_canvas_item_set ( markers[index],  */
/*  				"fill_color", HILITED_COLOR,  */
/*  				NULL); */
	
	if (hiliteindex >= 0 && hiliteindex != index) {
	    if (hiliteindex != curselection)
		gnome_canvas_item_set ( markers[hiliteindex], 
					"fill_color", CITY_COLOR, 
					NULL);
	    else
		gnome_canvas_item_set ( markers[hiliteindex], 
					"fill_color", SELECTED_COLOR, 
					NULL);
	}
	hiliteindex = index;

/*  	gnome_canvas_item_show (hilitemarker);  */
    } else {
/*  	gnome_canvas_item_hide (hilitemarker);  */
    }
    
    gnome_canvas_points_free (points);

    gtk_statusbar_pop ( GTK_STATUSBAR (statusbar), 1);
    gtk_statusbar_push ( GTK_STATUSBAR (statusbar), 1, loc->zone );
}

/* Handles case where cursor leaves the map */
static int
canvas_event (GtkWidget *canvas, GdkEvent *event, gpointer data)
{
    /* if pointer just left canvas, hide hilite marker(s) */
    if (event->type == GDK_LEAVE_NOTIFY) {
/*  	if (hilitemarker) */
/*  	    gnome_canvas_item_hide (hilitemarker); */
	if (hiliterubberband)
	    gnome_canvas_item_hide (hiliterubberband);
	if (hiliteindex >= 0 && hiliteindex != curselection)
	    gnome_canvas_item_set ( markers[hiliteindex], 
				    "fill_color", CITY_COLOR, 
				    NULL);

	gtk_statusbar_pop ( GTK_STATUSBAR (statusbar), 1);
	gtk_statusbar_push ( GTK_STATUSBAR (statusbar), 1, "" );
    }
    return FALSE;
}

/* Handles as motion and mouse button events in the map */
static gint
item_event (GnomeCanvasItem *item, GdkEvent *event, gpointer data)
{
    double longitude, latitude;
    double item_x, item_y;
    int    nearest;

    item_x = event->button.x;
    item_y = event->button.y;
    gnome_canvas_item_w2i (WorldMap->image_item, &item_x, &item_y);

    switch (event->type) {

	/* User selected a new location with a left mouse button press */
      case GDK_BUTTON_PRESS:
	switch (event->button.button) {
	  case 1:
	    
	    gnome_map_xlat_screen2map ( WorldMap, item_x, item_y,
					&longitude, &latitude );
	    
	    nearest  = find_nearest( longitude, latitude );

	    set_selection (nearest, TRUE);

	    break;
	    
	  default:
	    break;
	}
	
	break;
	
	/* highlight city which a button press will select */
      case GDK_MOTION_NOTIFY:

	gnome_map_xlat_screen2map ( WorldMap, item_x, item_y, 
				    &longitude, &latitude);

	nearest  = find_nearest( longitude, latitude );
	set_hilited (nearest, item_x, item_y);
	break;

      default:
	break;
    }
    
    return FALSE;
}

/* Handles events for the clist of locations */
static void
list_select_event ( GtkWidget *clist, gint row, gint column,
		    GdkEventButton *event, gpointer data)
{

    gchar       *text;
    gint        index;

    /* should we do anything? */
    if (ignore_locationlist_selectevents)
	return;

    /* msf - always read zero because sometimes col == -1 if they select */
    /*       without a mouse click (ie. keyboard navigation )            */
    gtk_clist_get_text(GTK_CLIST(clist), row, 0, &text);
    
    /* Just prints some information about the selected row */
    g_print("You selected row %d. More specifically you clicked in column %d, and the text in this cell is %s\n\n", row, column, text);
    
    index = find_location (text);
    if (index < 0)
	return;

    set_selection (index, FALSE);
    return;
}


static GnomeCanvasItem *
draw_city_marker ( GnomeMap *map, double longitude, double latitude)
{
    double  x, y;
    GnomeCanvasItem *item;
    GnomeCanvasGroup *canvas_root;

    canvas_root = gnome_canvas_root (GNOME_CANVAS (map->canvas));

    gnome_map_xlat_map2screen (map, longitude, latitude, &x, &y);

#define RAD 1
#ifdef ELLIPSE
    item = gnome_canvas_item_new (canvas_root,
				  gnome_canvas_ellipse_get_type (),
				  "x1", x-RAD,
				  "y1", y-RAD,
				  "x2", x+RAD,
				  "y2", y+RAD,
				  "fill_color", CITY_COLOR,
				  NULL);
#else
    item = gnome_canvas_item_new (canvas_root,
				  gnome_canvas_dot_get_type (),
				  "x", x,
				  "y", y,
				  "diameter_pixels", RAD,
				  "fill_color", CITY_COLOR,
				  NULL);
#endif
    
    setup_item ( item );
    return item;
}

static void
draw_cities (GnomeMap *map)
{
    gint i;

    if (markers)
	g_free(markers);

    markers = g_new( GnomeCanvasItem *, Locations->len);
    for (i=0; i < Locations->len; i++) {
	TimeZoneLocation  *loc = g_ptr_array_index (Locations, i);
    
	markers[i] = draw_city_marker (map, loc->longitude, loc->latitude);
    }
}

static void
view_menu_activate (GtkWidget *widget, void *data)
{
    static gint curitem = -1;
    gint   item = GPOINTER_TO_INT (data);

    double lat1, long1, lat2, long2;
    double dlat, dlong;

    if ( item == curitem )
	return;

    curitem = item; 

    /* compute aspect correct view and set canvas to it */
    /* we may have to shift view if it extends outside of map */
    if (Views[item].type == LONGITUDE_CONSTRAINT) {
	long1 = Views[item].constraint1;
	long2 = Views[item].constraint2;
	dlong = fabs(long2 - long1);
	dlat  = dlong/2.0;
	lat1  = Views[item].constraint3 - dlat/2.0;
	lat2  = Views[item].constraint3 + dlat/2.0;

	if (lat1 < -90.0) {
	    lat2 -= (lat1-90.0);
	    lat1 = -90.0;
	} else if (lat2 > 90.0) {
	    lat1 -= (lat2-90.0);
	    lat2 = 90.0;
	}
    } else if (Views[item].type == LATITUDE_CONSTRAINT) {
	lat1 = Views[item].constraint1;
	lat2 = Views[item].constraint2;
	dlat = fabs(lat2 - lat1);
	dlong = 2.0*dlat;
	long1 = Views[item].constraint3 - dlong/2.0;
	long2 = Views[item].constraint3 + dlong/2.0;

	if (long1 < -180.0) {
	    long2 -= (long1-180.0);
	    long1 = -180.0;
	} else if (long2 > 180.0) {
	    long1 -= (long2-180.0);
	    long2 = 180.0;
	}
    } else {
	g_warning ("Bad contraint type %d in Views structure item # %d.\n", 
		   item, Views[item].type);
	return;
    }

    gnome_map_set_view (WorldMap, long1, lat1, long2, lat2);

    /* make locationlist clist entries reflect those visible*/
    create_location_list (&locationlist);

}

GtkWidget *
create_view_menu ( void )
{
    GtkWidget *omenu;
    GtkWidget *menu;
    GtkWidget *menu_item;
    gint   i;

    omenu = gtk_option_menu_new ();

    menu = gtk_menu_new ();
    
    for  (i=0; i < numviews; i++) {
	menu_item = gtk_menu_item_new_with_label (_(Views[i].name));
	gtk_menu_append (GTK_MENU (menu), menu_item);

	gtk_signal_connect (GTK_OBJECT (menu_item), "activate",
			    (GtkSignalFunc) view_menu_activate, 
			    GINT_TO_POINTER (i));

	gtk_widget_show (menu_item);
    }
    gtk_option_menu_set_menu (GTK_OPTION_MENU (omenu), menu);
    gtk_option_menu_set_history (GTK_OPTION_MENU (omenu), 0);

    gtk_widget_show (omenu);
    return omenu;
}

/* returns pointer to the scrolled window containing the clist          */
/* pointer to clist is returned via the passed argument if it doesnt    */
/* already exist.  The list is clipped to the current world view        */
static GtkWidget *
create_location_list ( GtkWidget **returnlist )
{
    TimeZoneLocation   *loc;
    GtkWidget *scrolledwin;
    gchar *titles[] = { "Location", NULL };
    gchar *row[1];
    gint i;

    ignore_locationlist_selectevents = TRUE;

    if ( !*returnlist) {
	scrolledwin = gtk_scrolled_window_new (NULL, NULL);
    
	gtk_scrolled_window_set_policy (GTK_SCROLLED_WINDOW (scrolledwin),
					GTK_POLICY_AUTOMATIC, GTK_POLICY_ALWAYS);
	
	gtk_widget_show (scrolledwin);
	
	*returnlist = gtk_clist_new_with_titles (1, titles);
	gtk_clist_set_selection_mode (GTK_CLIST(*returnlist), 
				      GTK_SELECTION_BROWSE);
	gtk_clist_column_title_passive (GTK_CLIST(*returnlist), 0);
	gtk_signal_connect(GTK_OBJECT(*returnlist), "select_row",
			   GTK_SIGNAL_FUNC(list_select_event),
			   NULL);


	gtk_container_add (GTK_CONTAINER (scrolledwin), *returnlist);
    } else {
	gtk_clist_clear (GTK_CLIST (*returnlist));
	scrolledwin = NULL;
    }

    for (i=0; i < Locations->len; i++) {
	gint  newrow;

	loc = g_ptr_array_index (Locations, i);	
	if (!gnome_map_is_loc_in_view (WorldMap,loc->longitude,loc->latitude))
	    continue;

	row[0] = loc->zone;
	newrow = gtk_clist_append (GTK_CLIST (*returnlist), row);
	gtk_clist_set_row_data (GTK_CLIST (*returnlist), newrow, 
				GINT_TO_POINTER (i));
    }

    /* restore selection of location in list now we've recreated it */
    list_mark_location_selected(WorldMap, curselection, TRUE);

    gtk_widget_show (locationlist);

    ignore_locationlist_selectevents = FALSE;
    return scrolledwin;
}


int
main (int argc, char **argv)
{
    GtkWidget *frame;
    GtkWidget *hbox1, *hbox2;
    GtkWidget *vbox1, *vbox2;

    GtkWidget *viewcombo;

/*
    tzset ();
    printf ("tzname[0]=|%s|  tzname[1]=|%s|\n",tzname[0], tzname[1]);
*/
    gnome_init_with_popt_table("gglobe", "0.1", argc, argv, 
			       options, 0, NULL);
    
    /* load timezone data */
    Locations = loadTZDB ();
    if (!Locations) {
	g_warning (_("Cannot load timezone data"));
	exit (1);
    }
    
    mainwindow = gtk_window_new (GTK_WINDOW_TOPLEVEL);
    gtk_window_set_position (GTK_WINDOW (mainwindow), GTK_WIN_POS_CENTER);
    gtk_window_set_title (GTK_WINDOW (mainwindow), _("gglobe-canvas"));

    gtk_signal_connect (GTK_OBJECT (mainwindow), "destroy",
			GTK_SIGNAL_FUNC (gtk_main_quit), NULL);

    /* top-level hbox for packing map/statusbar and view combo/tz list box */
    hbox1 = gtk_hbox_new (FALSE, 2);
    gtk_container_add (GTK_CONTAINER (mainwindow), hbox1);

    /* create frame and world map first */
    vbox1 = gtk_vbox_new (FALSE, 2);
    gtk_box_pack_start (GTK_BOX (hbox1), vbox1, FALSE, FALSE, 0);

    frame = gtk_frame_new (NULL);
    gtk_box_pack_start (GTK_BOX (vbox1), frame, FALSE, FALSE, 0);

    WorldMap = gnome_map_new ( image, mapwidth, mapheight, aa );
    if (!WorldMap) {
	g_warning ("Could not create map view.");
	exit (1);
    }

    setup_item(WorldMap->image_item);
    gtk_signal_connect (GTK_OBJECT (WorldMap->canvas), "event",
			(GtkSignalFunc) canvas_event,
			NULL);

    gtk_container_add (GTK_CONTAINER (frame), WorldMap->canvas);

    statusbar = gtk_statusbar_new ();
    gtk_box_pack_start (GTK_BOX (vbox1), statusbar, FALSE, FALSE, 0);
    gtk_statusbar_push (GTK_STATUSBAR (statusbar), 1, "Unselected");
    gtk_widget_show (statusbar);

    /* add View combo box */
    frame = gtk_frame_new (NULL);
    gtk_box_pack_start (GTK_BOX (hbox1), frame, FALSE, FALSE, 2);

    vbox2 = gtk_vbox_new (FALSE, 2);
    gtk_container_add (GTK_CONTAINER (frame), vbox2);

    hbox2 = gtk_hbox_new (FALSE, 2);
    gtk_box_pack_start (GTK_BOX (vbox2), hbox2, FALSE, FALSE, 2);
    
    viewcombo = create_view_menu ();
    gtk_box_pack_start (GTK_BOX (hbox2), gtk_label_new (_("View: ")),
			FALSE, FALSE, 0);
    gtk_box_pack_start (GTK_BOX (hbox2), viewcombo, FALSE, FALSE, 2);

    /* put cities on the world map */
    draw_cities (WorldMap);

    /* add list of all timezones */
    frame = gtk_frame_new (NULL);
    gtk_box_pack_start (GTK_BOX (vbox2), 
			create_location_list (&locationlist), 
			TRUE, TRUE, 2);
    
    /* display and wait */
    gtk_widget_show_all (mainwindow);

    /* pick New York City as default */
    set_selection (find_location (_("America/New_York")), TRUE);

    gtk_main ();
    
    return 0;
}

