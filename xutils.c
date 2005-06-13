/*
 * xutils.c - a Python wrapper for common Xlib ops
 *
 * Michael Fulbright <msf@redhat.com>
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


#include <Python.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>

static PyObject * getRootResources(PyObject *s, PyObject *args);
static PyObject * setRootResource(PyObject * s, PyObject * args);
static PyObject * screenHeight (PyObject * s, PyObject * args);
static PyObject * screenWidth (PyObject * s, PyObject * args);

static PyMethodDef xutilsMethods[] = {
    { "getRootResources", getRootResources, 1, NULL },
    { "setRootResource", setRootResource, 1, NULL },
    { "screenHeight", screenHeight, 1, NULL },
    { "screenWidth", screenWidth, 1, NULL },
    { NULL, NULL, 0, NULL }
};

typedef struct _Resource {
    char *key, *val;
} Resource;


static int
openDisplay(Display **dpy, Window *root) 
{
    int     scrn;

    *dpy=XOpenDisplay("");
    if (!*dpy)
	return -1;

    scrn=DefaultScreen(*dpy);
    *root = RootWindow(*dpy, scrn);
    return 0;
}

static void
closeDisplay(Display *dpy)
{
   XCloseDisplay(dpy);
}    

static Resource **
getCurrentResources(Display *dpy)
{
    char *resource_string, *p;
    Resource **rc;
    int  nrec;

    /* read through current resources, split on newlines */
    resource_string = XResourceManagerString(dpy);

    if (!resource_string)
	return NULL;

    rc = (Resource **)malloc(sizeof(Resource *));
    p = resource_string;
    nrec = 0;
    while (1) {
	char *eol;
	char *sep;
	int nleft;

	/* find next newline, defines end of current record */
	eol = strchr(p, '\n');

	if (!eol)
	    break;

	/* find colon separating key and value */
	/* if no colon skip this record        */
	sep = strchr(p, ':');
	if (sep) {
	    int  len;
	    Resource *newrec;

	    newrec = (Resource *) malloc(sizeof(Resource));

	    len = sep - p + 1;
	    newrec->key = (char *) malloc(len*sizeof(char));
	    memcpy(newrec->key, p, len);
	    newrec->key[len-1] = '\0';

	    len = eol - sep;
	    newrec->val = (char *) malloc(len*sizeof(char));
	    memcpy(newrec->val, sep+1, len);
	    newrec->val[len-1] = '\0';

	    rc = (Resource **) realloc(rc, (nrec+1) * sizeof(Resource *));
	    rc[nrec] = newrec;
	    nrec = nrec + 1;
	}

	nleft = strlen(resource_string) - (eol-resource_string);
	if (nleft <= 0)
	    break;

	p = eol + 1;
    }

    if (nrec > 0) {
	rc = (Resource **) realloc(rc, (nrec+1) * sizeof(Resource *));
	rc[nrec] = NULL;
    } else {
	rc = NULL;
    }

    return rc;
}

static void
freeResources(Resource **rc)
{
    int idx;

    if (!rc)
	return;

    idx = 0;
    while (rc[idx]) {
	free(rc[idx]->key);
	free(rc[idx]->val);
	free(rc[idx]);

	idx++;
    }

    free(rc);
}

/* return dictionary of resources on root display */
PyObject *
getRootResources(PyObject *s, PyObject *args) {
    Display *dpy;
    Window  root;
    Resource **resources, **p;
    PyObject *rc;

    if (openDisplay(&dpy, &root) < 0) {
	PyErr_SetString(PyExc_SystemError, "Could not open display.");
	return NULL;
    }
	
    resources = getCurrentResources(dpy);
    if (!resources) {
	closeDisplay(dpy);
	Py_INCREF(Py_None);
	return Py_None;
    }

    rc = PyDict_New();
    p = resources;
    while (*p) {
	PyDict_SetItemString(rc, (*p)->key,  Py_BuildValue("s", (*p)->val));
	p++;
    }

    freeResources(resources);
    closeDisplay(dpy);

    return rc;
}

static PyObject *
setRootResource(PyObject *s, PyObject *args)
{
    Display *dpy;
    Window  root;
    Resource **resources, **p;
    char *key, *val, *rstring;
    int fnd, nrec;

    if (!PyArg_ParseTuple(args, "ss", &key, &val)) {
	return NULL;
    }

    if (openDisplay(&dpy, &root) < 0) {
	PyErr_SetString(PyExc_SystemError, "Could not open display.");
	return NULL;
    }

    resources = getCurrentResources(dpy);
    fnd = 0;
    nrec = 0;
    if (resources) {
	p = resources;
	while (*p) {
	    if (!strcmp(key, (*p)->key)) {
		free((*p)->val);
		(*p)->val = strdup(val);
		fnd = 1;
		break;
	    }

	    p++;
	}

	p = resources;
	while (*p) {
	    nrec++;
	    p++;
	}
    }

    if (!fnd) {
	Resource *newrec;

	newrec = (Resource *) malloc(sizeof(Resource));
	newrec->key = strdup(key);
	newrec->val = strdup(val);

	if (nrec > 0)
	    resources = (Resource **) realloc(resources, (nrec+2) * sizeof(Resource *));
	else
	    resources = (Resource **) malloc(2*sizeof(Resource *));

	resources[nrec] = newrec;
	resources[nrec+1] = NULL;
    }

    rstring = NULL;
    p = resources;
    while (*p) {
	int len;
	char *tmpstr;

	len = strlen((*p)->key) + strlen((*p)->val) + 3;
	tmpstr = (char *) malloc(len*sizeof(char));
	strcpy(tmpstr, (*p)->key);
	strcat(tmpstr, ":");
	strcat(tmpstr, (*p)->val);
	strcat(tmpstr, "\n");

	if (rstring) {
	    rstring = (char *)realloc(rstring, (strlen(rstring)+len+1)*sizeof(char));
	    strcat(rstring, tmpstr);
	} else {
	    rstring = tmpstr;
	}

	p++;
    }

    XChangeProperty(dpy, root, XA_RESOURCE_MANAGER, XA_STRING, 
		    8, PropModeReplace, (unsigned char *)rstring,
		    strlen(rstring));

    free(rstring);
    freeResources(resources);

    closeDisplay(dpy);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
screenHeight(PyObject *s, PyObject *args)
{
    Display *dpy;
    Window  root;
    int     scrn;
    PyObject *rc;

    if (openDisplay(&dpy, &root) < 0) {
	PyErr_SetString(PyExc_SystemError, "Could not open display.");
	return NULL;
    }

    scrn=DefaultScreen(dpy);

    rc = Py_BuildValue("i", DisplayHeight(dpy, scrn));

    closeDisplay(dpy);
    return rc;
}

static PyObject *
screenWidth(PyObject *s, PyObject *args)
{
    Display *dpy;
    Window  root;
    int     scrn;
    PyObject *rc;

    if (openDisplay(&dpy, &root) < 0) {
	PyErr_SetString(PyExc_SystemError, "Could not open display.");
	return NULL;
    }

    scrn=DefaultScreen(dpy);

    rc = Py_BuildValue("i", DisplayWidth(dpy, scrn));

    closeDisplay(dpy);
    return rc;
}

void 
initxutils ()
{
    PyObject * d;

    d = Py_InitModule ("xutils", xutilsMethods);
}
