/*
 * xmouse.c - a Python wrapper for XFree86's misc extention's mouse
 *            functions.
 *
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 2000 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include <X11/Intrinsic.h>
#include <X11/Xmd.h>
#include <X11/extensions/xf86misc.h>
#include <X11/Xos.h>
#include <X11/X.h>
#include <Python.h>

static char *Mouses[] = { "None", "Microsoft", "MouseSystems", "MMSeries",
			    "Logitech", "BusMouse", "Mouseman", "PS/2",
			    "MMHitTab", "GlidePoint", "IntelliMouse",
			    "ThinkingMouse", "IMPS/2", "ThinkingMousePS/2",
			    "MouseManPlusPS/2", "GlidePointPS/2", 
			    "NetMousePS/2", "NetScrollPS/2", "SysMouse",
			    "Auto", "Xqueue", "OSMouse" };
static int numMouses = (sizeof (Mouses) / sizeof (*Mouses));

static int (*olderror)();
static char error[512];
static int error_set = FALSE;

static PyObject * mouse_get (PyObject * s, PyObject * args);
static PyObject * mouse_reopen (PyObject * s, PyObject * args);

/*  static PyObject * mouse_set (PyObject * s, PyObject * args); */

static PyMethodDef xmouseMethods[] = {
    { "get", mouse_get, 1 },
    { "reopen", mouse_reopen, 1 },
/*  { "set", mouse_set, 1 }, */
    { NULL, NULL }
};

static int miscError(Display *disp, XErrorEvent *err)
{
    XGetErrorText (disp, err->error_code, error, 512);
    error_set = TRUE;
    return 0;
}

PyObject *
mouse_get (PyObject * s, PyObject * args)
{
    XF86MiscMouseSettings settings;
    char *name;
    PyObject *ret;
	
    Display *disp = XOpenDisplay (NULL);
    if (!disp) {
	PyErr_SetString(PyExc_RuntimeError, "Unable to open display");
	return NULL;
    }
	
    if (!XF86MiscGetMouseSettings(disp, &settings)) {
	PyErr_SetString(PyExc_RuntimeError, "Unable to get mouse settings");
	XCloseDisplay (disp);
	return NULL;
    }

    if (settings.type == MTYPE_XQUEUE)
	name = "Xqueue";
    else if (settings.type == MTYPE_OSMOUSE)
	name = "OSMouse";
    else if (settings.type < 0 || (settings.type >= numMouses))
	name = "Unknown";
    else
	name = Mouses[settings.type+1];

    ret = Py_BuildValue("ssiiiisisss",
			settings.device == NULL ? "no device": settings.device,
			name,
			settings.baudrate,
			settings.samplerate,
			settings.resolution,
			settings.buttons,
			settings.emulate3buttons ? "on": "off",
			settings.emulate3timeout,
			settings.chordmiddle ? "on": "off",
			settings.flags & MF_CLEAR_DTR ? "ClearDTR" : "NoClearDTR",
			settings.flags & MF_CLEAR_DTR ? "ClearRTS" : "NoClearRTS");

    if (settings.device) {
	free(settings.device);
    }
    XCloseDisplay (disp);
    
    return ret;
}

PyObject *
mouse_reopen (PyObject * s, PyObject * args)
{
    XF86MiscMouseSettings settings;
    Status rc;
    
    Display *disp = XOpenDisplay (NULL);
    if (!disp) {
	PyErr_SetString(PyExc_RuntimeError, "Unable to open display");
	return NULL;
    }
	
    if (!XF86MiscGetMouseSettings(disp, &settings)) {
	PyErr_SetString(PyExc_RuntimeError, "Unable to get mouse settings");
	XCloseDisplay (disp);
	return NULL;
    }
    settings.flags |= MF_REOPEN;

    XSync(disp, False);
    olderror = XSetErrorHandler(miscError);
    rc = XF86MiscSetMouseSettings(disp, &settings);
    XSync(disp, False);
    XSetErrorHandler(olderror);
    XCloseDisplay (disp);
    if (error_set) {
	PyErr_SetString(PyExc_RuntimeError, error);
	error_set = 0;
	return NULL;
    }
    if (!rc) {
	PyErr_SetString(PyExc_RuntimeError, "unknown error reopening mouse device");
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

void 
initxmouse ()
{
    Py_InitModule ("xmouse", xmouseMethods);
}
