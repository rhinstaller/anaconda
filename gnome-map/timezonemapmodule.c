/* Copyright (C) 1999 Red Hat, Inc. */
/* Original work by Michael Fulbright <drmike@redhat.com> */

#include <gnome.h>
#include <stdlib.h>
#include <unistd.h>
#include <math.h>

#include <Python.h>

#include "pygtk.h"
#include "gnome-map.h"
#include "gnome-canvas-dot.h"
#include "timezones.h"


/* Command line options */
/* image     - filename of file to use for map (must be PNG for antialias) */
/* mapwidth  - width to scale image to (also size of canvas widget)        */
/* mapheight - height to scale image to (also size of canvas widget)       */
/* aa        - if TRUE use antialiased canvas instead of normal            */

typedef struct MapData_t {
    GnomeMap *map;
    GtkWidget * locationlist;
    GtkWidget * citylist;
    GtkWidget * statusbar;
    GtkWidget * views;
    gint curselection;
    GnomeCanvasItem *selmarker;
    GnomeCanvasItem *curmarker;
    GnomeCanvasItem **markers;
    GPtrArray *Locations;
    GnomeCanvasItem *hiliterubberband;
    gint hiliteindex;
} MapData;

/* if TRUE we do not want to act on the select_row events to locationlist */
/* used when we are manually manipulating rows in locationlist and we     */
/* want to ignore the events going to the callback.                       */
gboolean ignore_locationlist_selectevents=FALSE;

/* Canvas item circle for selected location */
double          oldselx, oldsely; /* old location of selection */
#define SELECTED_COLOR "red"
#define HILITED_COLOR   "limegreen"
#define CITY_COLOR     "yellow"

GnomeMap *WorldMap;

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
    { "World",         LONGITUDE_CONSTRAINT, -180.0, 180.0, 0.0 },
    { "North America", LONGITUDE_CONSTRAINT, -171.0, -21.0, 40.0 },
    { "South America", LATITUDE_CONSTRAINT,   15.0,   -70.0, -70.0 },
    { "Pacific Rim",   LATITUDE_CONSTRAINT,    -47.0, 47.0, 155.0},
    { "Europe",        LONGITUDE_CONSTRAINT,  -25.0, 70.0, 45.0 },
    { "Africa",        LATITUDE_CONSTRAINT,   40.0,   -40.0, 15.0},
    { "Asia",          LONGITUDE_CONSTRAINT,  20.0, 165.0, 40.0}
};

static gint numviews = sizeof(Views)/sizeof(ViewDefinition);

static gint item_event (GnomeCanvasItem *item, GdkEvent *event, gpointer data);
static GtkWidget * create_location_list (MapData *mapdata);

/* give a location name search for match in Locations db */
/* returns index if found, -1 if not                     */
static int
find_location (GPtrArray *Locations, gchar *locname)
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
find_nearest (GPtrArray * Locations, double longitude, double latitude )
{
    double mindist;
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
setup_item (GnomeCanvasItem *item, MapData *mapdata)
{
    gtk_signal_connect (GTK_OBJECT (item), "event",
			(GtkSignalFunc) item_event,
			mapdata);
}

/* Moves marker (a 'x' currently) to the specified location */
/* and sets it to the specified color.  The oldx and oldy      */
/* variables are required because the canvas only allows one   */
/* to do relative moves for items.  These are automatically    */
/* set to x and y by this function before it returns.          */
/*                                                             */
/* The first time this function is called for a given marker   */
/* *curmarker should equal NULL.  The marker will be created   */
/* automatically.                                              */

static void
set_flag_marker (MapData *mapdata, gchar *color,
		 double x, double y, double *oldx, double *oldy)
{
    GnomeCanvasGroup  *canvas_root;
    GnomeCanvasItem   *group;

    g_return_if_fail ( color != NULL );

    canvas_root = gnome_canvas_root (GNOME_CANVAS(WorldMap->canvas));
    if (!mapdata->curmarker) {
	group = gnome_canvas_item_new ( canvas_root,
					gnome_canvas_group_get_type(),
					"x", x,
					"y", y,
					NULL);
	
#define MARKER_RADIUS 3.5
#define MARKER_WIDTH_PIX 1

        setup_item (gnome_canvas_item_new (GNOME_CANVAS_GROUP (group),
					   gnome_canvas_text_get_type (),
					   "font", "-adobe-helvetica-bold-r-normal--12-*-*-*-p-*-*-*",
					   "anchor", GTK_ANCHOR_CENTER,
					   "fill_color", "red",
					   "text", "x",
					   NULL), mapdata);

  	mapdata->curmarker = GNOME_CANVAS_ITEM (group); 
    } else {
	gnome_canvas_item_move (mapdata->curmarker, x - *oldx, y - *oldy);
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
    MapData *mapdata = (MapData *) map->data;
    
    g_return_if_fail ( map != NULL );
    g_return_if_fail ( index >= 0 );

    loc = g_ptr_array_index (mapdata->Locations, index);
    
    gnome_map_xlat_map2screen ( map, 
				loc->longitude,	loc->latitude,
				&selx, &sely );
    set_flag_marker (mapdata, SELECTED_COLOR, selx, sely, &oldselx, &oldsely);
    
    if (mapdata->curselection >= 0) {
	gnome_canvas_item_set (mapdata->markers[mapdata->curselection],
			       "fill_color", CITY_COLOR, NULL);
	gnome_canvas_item_show (mapdata->markers[mapdata->curselection]);
    }

    gnome_canvas_item_hide (mapdata->markers[index]);
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
    MapData * mapdata;

    mapdata = (MapData *) map->data;
    
    /* We're messing with list manually, so let callback know to */
    /* ignore any events till we're done                         */
    ignore_locationlist_selectevents = TRUE;

    /* if current selection is visible then select it again, otherwise */
    /* change clist to not have a current selection                    */
    if (index >= 0) {
	TimeZoneLocation *loc = g_ptr_array_index (mapdata->Locations, index);
	
	if (gnome_map_is_loc_in_view (map,loc->longitude,loc->latitude)) {
	    gtk_clist_set_selection_mode (GTK_CLIST (mapdata->locationlist), 
					  GTK_SELECTION_BROWSE);
	} else {
	    gtk_clist_set_selection_mode (GTK_CLIST (mapdata->locationlist), 
					  GTK_SELECTION_SINGLE);
	}
    }

    /* find in list of locations and set as current */
    newrow = gtk_clist_find_row_from_data (GTK_CLIST (mapdata->locationlist),
					   GINT_TO_POINTER (index));

    if (newrow >= 0 ) {
	gtk_clist_select_row (GTK_CLIST(mapdata->locationlist), newrow, 0);
	if (jumpto && gtk_clist_row_is_visible (GTK_CLIST (mapdata->locationlist), newrow) != GTK_VISIBILITY_FULL) {
	    gtk_clist_moveto (GTK_CLIST (mapdata->locationlist), newrow , 0, 0.5, 0.5 );
	}
    }

    /* We're done mucking with clist, ok to listen to events again */
    ignore_locationlist_selectevents = FALSE;

}
/* handles all canvas drawing for making the selected location # index */
/* in the sorted list in the Locations variable                        */
static void
set_selection (MapData *mapdata, gint index, gboolean jumpto)
{
    g_return_if_fail ( index >= 0 );

    map_mark_location_selected (WorldMap, index);

    list_mark_location_selected (WorldMap, index, jumpto);

    /* NOTE: curselection is global variable. Only place it gets set */
    mapdata->curselection = index;
}

/* Given an index into the Locations db and a position, draw the hilite */
/* marker around it to indicate it is city cursor is pointing at        */
static void
set_hilited (MapData *mapdata, gint index, double item_x, double item_y)
{
    TimeZoneLocation *loc;
    GnomeCanvasPoints *points;

    g_return_if_fail ( index >= 0 );

    loc = g_ptr_array_index (mapdata->Locations, index);

    points = gnome_canvas_points_new (2);
    points->coords[0] = item_x;
    points->coords[1] = item_y;
    gnome_map_xlat_map2screen ( WorldMap,
				loc->longitude, loc->latitude,
				&points->coords[2], &points->coords[3] );
    if (mapdata->hiliterubberband) {
	gnome_canvas_item_set (mapdata->hiliterubberband, "points", points, NULL);
	gnome_canvas_item_show (mapdata->hiliterubberband);
    } else {
	GnomeCanvasGroup *canvas_root = gnome_canvas_root (GNOME_CANVAS (WorldMap->canvas));
	
	mapdata->hiliterubberband =
	    gnome_canvas_item_new (canvas_root,
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
	setup_item (mapdata->hiliterubberband, mapdata);
    }

    /* if hilited city isn't also currently selected city, draw the */
    /* hilite marker as well                                        */
    if (index != mapdata->curselection) {
	
	if (mapdata->hiliteindex >= 0 && mapdata->hiliteindex != index) {
	    if (mapdata->hiliteindex != mapdata->curselection)
		gnome_canvas_item_set (mapdata->markers[mapdata->hiliteindex], 
				       "fill_color", CITY_COLOR, 
				       NULL);
	    else
		gnome_canvas_item_set (mapdata->markers[mapdata->hiliteindex], 
				       "fill_color", SELECTED_COLOR, 
				       NULL);
	}
	mapdata->hiliteindex = index;
	gtk_statusbar_pop (GTK_STATUSBAR (mapdata->statusbar), 1);
	gtk_statusbar_push (GTK_STATUSBAR (mapdata->statusbar), 1, loc->zone );
    }
    
    gnome_canvas_points_free (points);
}

/* Handles case where cursor leaves the map */
static int
canvas_event (GtkWidget *canvas, GdkEvent *event, gpointer data)
{
    MapData *mapdata = (MapData *) data;
    
    /* if pointer just left canvas, hide hilite marker(s) */
    if (event->type == GDK_LEAVE_NOTIFY) {
	if (mapdata->hiliterubberband)
	    gnome_canvas_item_hide (mapdata->hiliterubberband);
	if (mapdata->hiliteindex >= 0 &&
	    mapdata->hiliteindex != mapdata->curselection)
	    gnome_canvas_item_set (mapdata->markers[mapdata->hiliteindex], 
				    "fill_color", CITY_COLOR, 
				    NULL);

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
    MapData *mapdata = (MapData *) data;

    item_x = event->button.x;
    item_y = event->button.y;
    gnome_canvas_item_w2i (WorldMap->image_item, &item_x, &item_y);

    switch (event->type) {

	/* User selected a new location with a left mouse button press */
      case GDK_BUTTON_PRESS:
	switch (event->button.button) {
	  case 1:
	    
	    gnome_map_xlat_screen2map (WorldMap, item_x, item_y,
				       &longitude, &latitude);
	    
	    nearest  = find_nearest(mapdata->Locations, longitude, latitude);

	    set_selection (mapdata, nearest, TRUE);

	    break;
	    
	  default:
	    break;
	}
	
	break;
	
	/* highlight city which a button press will select */
      case GDK_MOTION_NOTIFY:

	gnome_map_xlat_screen2map ( WorldMap, item_x, item_y, 
				    &longitude, &latitude);

	nearest  = find_nearest(mapdata->Locations, longitude, latitude);
	set_hilited (mapdata, nearest, item_x, item_y);
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
    MapData * mapdata = (MapData *) data;

    /* should we do anything? */
    if (ignore_locationlist_selectevents)
	return;

    /* msf - always read zero because sometimes col == -1 if they select */
    /*       without a mouse click (ie. keyboard navigation )            */
    gtk_clist_get_text(GTK_CLIST(clist), row, 0, &text);
    
    /* Just prints some information about the selected row */
    g_print("You selected row %d. More specifically you clicked in column %d, and the text in this cell is %s\n\n", row, column, text);
    
    index = find_location (mapdata->Locations, text);
    if (index < 0)
	return;

    set_selection (mapdata, index, FALSE);
    return;
}


static GnomeCanvasItem *
draw_city_marker ( GnomeMap *map, double longitude, double latitude)
{
    double  x, y;
    GnomeCanvasItem *item;
    GnomeCanvasGroup *canvas_root;
    MapData *mapdata = (MapData *) map->data;

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
    
    setup_item (item, mapdata);
    return item;
}

static void
draw_cities (GnomeMap *map)
{
    gint i;
    MapData * mapdata = (MapData *) map->data;
    
    if (mapdata->markers)
	g_free(mapdata->markers);

    mapdata->markers = g_new( GnomeCanvasItem *, mapdata->Locations->len);
    for (i=0; i < mapdata->Locations->len; i++) {
	TimeZoneLocation  *loc = g_ptr_array_index (mapdata->Locations, i);
    
	mapdata->markers[i] = draw_city_marker (map, loc->longitude, loc->latitude);
    }
}

static void
view_menu_activate (GtkWidget *widget, void *data)
{
    static gint curitem = -1;
    gint   item = GPOINTER_TO_INT (data);
    MapData *mapdata = gtk_object_get_data (GTK_OBJECT (widget), "mapdata");
    
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
    create_location_list (mapdata);
}

GtkWidget *
create_view_menu (MapData *mapdata)
{
    GtkWidget *omenu;
    GtkWidget *menu;
    GtkWidget *menu_item;
    gint   i;

    omenu = gtk_option_menu_new ();

    menu = gtk_menu_new ();
    
    for  (i=0; i < numviews; i++) {
	menu_item = gtk_menu_item_new_with_label (Views[i].name);
	gtk_menu_append (GTK_MENU (menu), menu_item);

	gtk_signal_connect (GTK_OBJECT (menu_item), "activate",
			    (GtkSignalFunc) view_menu_activate, 
			    GINT_TO_POINTER (i));

	gtk_object_set_data (GTK_OBJECT (menu_item), "mapdata", mapdata);
    
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
create_location_list (MapData *mapdata)
{
    TimeZoneLocation   *loc;
    GtkWidget *scrolledwin;
    gchar *titles[] = { "Location", NULL };
    gchar *row[1];
    gint i;

    ignore_locationlist_selectevents = TRUE;

    if (! mapdata->locationlist) {
	scrolledwin = gtk_scrolled_window_new (NULL, NULL);
    
	gtk_scrolled_window_set_policy (GTK_SCROLLED_WINDOW (scrolledwin),
					GTK_POLICY_AUTOMATIC, GTK_POLICY_ALWAYS);
	
	gtk_widget_show (scrolledwin);
	
	mapdata->locationlist = gtk_clist_new_with_titles (1, titles);
	
	gtk_clist_set_selection_mode (GTK_CLIST(mapdata->locationlist), 
				      GTK_SELECTION_BROWSE);
	gtk_clist_column_title_passive (GTK_CLIST(mapdata->locationlist), 0);
	gtk_signal_connect(GTK_OBJECT(mapdata->locationlist), "select_row",
			   GTK_SIGNAL_FUNC(list_select_event),
			   mapdata);

	gtk_container_add (GTK_CONTAINER (scrolledwin), mapdata->locationlist);
    } else {
	gtk_clist_clear (GTK_CLIST (mapdata->locationlist));
	scrolledwin = NULL;
    }

    for (i=0; i < mapdata->Locations->len; i++) {
	gint  newrow;

	loc = g_ptr_array_index (mapdata->Locations, i);	
	if (!gnome_map_is_loc_in_view (WorldMap, loc->longitude, loc->latitude))
	    continue;

	row[0] = loc->zone;
	newrow = gtk_clist_append (GTK_CLIST (mapdata->locationlist), row);
	gtk_clist_set_row_data (GTK_CLIST (mapdata->locationlist), newrow, 
				GINT_TO_POINTER (i));
    }

    /* restore selection of location in list now we've recreated it */
    list_mark_location_selected(WorldMap, mapdata->curselection, TRUE);

    ignore_locationlist_selectevents = FALSE;
    return scrolledwin;
}

MapData * new_mapdata (char * path)
{
    MapData * mapdata;
    mapdata = g_new0 (MapData, 1);

    /* make a new map view */
    WorldMap = gnome_map_new (path, 390, 180, FALSE);
    if (!WorldMap) {
	g_warning ("Could not create map view.");
	return NULL;
    }
    WorldMap->data = mapdata;
    mapdata->map = WorldMap;

    setup_item (WorldMap->image_item, mapdata);
    gtk_signal_connect (GTK_OBJECT (WorldMap->canvas), "event",
			(GtkSignalFunc) canvas_event,
			mapdata);

    /* load timezone data */
    mapdata->Locations = loadTZDB ();
    if (!mapdata->Locations) {
	g_warning (_("Cannot load timezone data"));
	return NULL;
    }

    mapdata->citylist = create_location_list (mapdata);
    draw_cities (WorldMap);

    mapdata->statusbar = gtk_statusbar_new ();
    mapdata->views = create_view_menu (mapdata);
    
    return mapdata;
}

#if 0
int
main (int argc, char **argv)
{
    GtkWidget *frame;
    GtkWidget *hbox1, *hbox2;
    GtkWidget *vbox1, *vbox2;
    GtkWidget *viewcombo;
    GtkWidget *statusbar;
    GtkWidget *aframe;
    GtkWidget *mainwindow;
    MapData *mapdata;

    gnome_init ("gglobe", "0.1", argc, argv);

    mapdata = new_mapdata ();
    
    mainwindow = gtk_window_new (GTK_WINDOW_TOPLEVEL);
    gtk_window_set_position (GTK_WINDOW (mainwindow), GTK_WIN_POS_CENTER);
    gtk_window_set_title (GTK_WINDOW (mainwindow), _("gglobe-canvas"));

    gtk_container_add (GTK_CONTAINER (mainwindow), WorldMap->canvas);

    gtk_widget_show (statusbar);

    /* add View combo box */
    aframe = gtk_frame_new (NULL);
    gtk_box_pack_start (GTK_BOX (hbox1), frame, FALSE, FALSE, 2);

    vbox2 = gtk_vbox_new (FALSE, 2);
    gtk_container_add (GTK_CONTAINER (frame), vbox2);

    hbox2 = gtk_hbox_new (FALSE, 2);
    gtk_box_pack_start (GTK_BOX (vbox2), hbox2, FALSE, FALSE, 2);
     
    viewcombo = create_view_menu (mapdata);
    gtk_box_pack_start (GTK_BOX (hbox2), gtk_label_new ("View: "),
			FALSE, FALSE, 0);
    gtk_box_pack_start (GTK_BOX (hbox2), viewcombo, FALSE, FALSE, 2);

    /* put cities on the world map */

    /* add list of all timezones */
    frame = gtk_frame_new (NULL);
    gtk_box_pack_start (GTK_BOX (vbox2), 
			create_location_list (mapdata), 
			TRUE, TRUE, 2);
    
    /* display and wait */
    gtk_widget_show_all (mainwindow);

    /* pick New York City as default */
    set_selection (mapdata,
		   find_location (mapdata->Locations, "America/New_York"),
		   TRUE);

    gtk_main ();
    
    return 0;
}

#endif

static PyMethodDef tzObjectMethods[] = {
    { NULL },
};

typedef struct tzObject_t {
    PyObject_HEAD;
    MapData * mapdata;
} tzObject;

/*  typedef struct tzObject_t tzObject; */

static PyObject * tzGetAttr(tzObject * o, char * name);
static void tzDealloc (tzObject * o);

static PyTypeObject tzType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,				/* ob_size */
	"timezonemap",			/* tp_name */
	sizeof(tzObject),		/* tp_size */
	0,				/* tp_itemsize */
	(destructor) tzDealloc, 	/* tp_dealloc */
	0,				/* tp_print */
	(getattrfunc) tzGetAttr, 	/* tp_getattr */
	0,				/* tp_setattr */
	0,				/* tp_compare */
	0,				/* tp_repr */
	0,				/* tp_as_number */
	0,				/* tp_as_sequence */
	0,				/* tp_as_mapping */
};

static PyObject * tzGetAttr(tzObject * o, char * name) {
    if (!strncmp (name, "map", 3)) {
	return PyGtk_New((GtkObject *) o->mapdata->map->canvas);
    }
    if (!strncmp (name, "citylist", 8)) {
	return PyGtk_New((GtkObject *) o->mapdata->citylist);
    }
    if (!strncmp (name, "statusbar", 9)) {
	return PyGtk_New((GtkObject *) o->mapdata->statusbar);
    }
    if (!strncmp (name, "views", 5)) {
	return PyGtk_New((GtkObject *) o->mapdata->views);
    }
    return Py_FindMethod(tzObjectMethods, (PyObject *) o, name);
};

static void tzDealloc (tzObject * o)
{
    return;
}

static tzObject * doNewTZ (PyObject * s, PyObject * args);

static PyMethodDef timezoneMethods[] = {
    { "new", (PyCFunction) doNewTZ, METH_VARARGS, NULL },
    { NULL },
};

static tzObject * doNewTZ (PyObject * s, PyObject * args) {
    tzObject *o;
    char * path;
    
    if (!PyArg_ParseTuple(args, "s", &path))
	return NULL;
        
    o = (tzObject *) PyObject_NEW(tzObject, &tzType);
    
    o->mapdata = new_mapdata (path);
    
    if (!WorldMap || !o->mapdata) {
	PyErr_SetString(PyExc_TypeError, "Could not create map view.");
	return NULL;
    }

    return o;
}

#include <gdk_imlib.h>

void inittimezonemap (void) {
    init_pygtk();
    
    Py_InitModule("timezonemap", timezoneMethods);
}
