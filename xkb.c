#include <stdio.h>
#include <Python.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/extensions/XKBrules.h>
#include <assert.h>

#define max(a,b) ((a) > (b) ? (a) : (b))
#define min(a,b) ((a) < (b) ? (a) : (b))

#define MAX_COMPONENTS 400
#define XKB_RULES "/usr/X11R6/lib/X11/xkb/rules/xfree86"

PyObject *list_rules ();

static PyMethodDef _xkbMethods[] = {
    { "list_rules", list_rules, 1 },
    { NULL, NULL }
};

void 
init_xkb ()
{
  PyObject *m;
  m = Py_InitModule ("_xkb", _xkbMethods);

  if (PyErr_Occurred ())
    Py_FatalError ("can't initialize module _xkb");
}

PyObject * 
list_rules ()
{
  PyObject *models, *layouts, *variants, *options, *rules;
  XkbRF_RulesPtr list;
  Bool result;
  int num_comp;
  int i;

  list = XkbRF_Create (0,0);
  result = XkbRF_LoadDescriptionsByName (XKB_RULES, NULL, list);

  models = PyDict_New ();
  num_comp = min (list->models.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (list->models.desc[i].name);
      desc = PyString_FromString (list->models.desc[i].desc);
      PyDict_SetItem (models, name, desc);
    }

  layouts = PyDict_New ();
  num_comp = min (list->layouts.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (list->layouts.desc[i].name);
      desc = PyString_FromString (list->layouts.desc[i].desc);
      PyDict_SetItem (layouts, name, desc);
    }
  
  variants = PyDict_New ();
  num_comp = min (list->variants.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (list->variants.desc[i].name);
      desc = PyString_FromString (list->variants.desc[i].desc);
      PyDict_SetItem (variants, name, desc);
    }

  options = PyDict_New ();
  num_comp = min (list->options.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (list->options.desc[i].name);
      desc = PyString_FromString (list->options.desc[i].desc);
      PyDict_SetItem (options, name, desc);
    }

  XkbRF_Free (list,True);

  rules = PyTuple_New (4);

  PyTuple_SET_ITEM (rules, 0, models);
  PyTuple_SET_ITEM (rules, 1, layouts);
  PyTuple_SET_ITEM (rules, 2, variants);
  PyTuple_SET_ITEM (rules, 3, options);

  return rules;
}

int main (int argc, char **argv)
{
  int major, minor, event, error, reason;
  int max;
  int i;
  Display *dpy;
  XkbComponentNamesRec ptrns = { NULL, NULL, NULL, NULL, NULL, "*" };
  XkbComponentListPtr comps;
  XkbDescPtr xkb;


  major = XkbMajorVersion;
  minor = XkbMinorVersion;
/*    if (!XkbQueryExtension(dpy, &op, &event, &error, &major, &minor))  */
/*      { */
/*        fprintf (stderr, "no xkb\n"); */
/*      } */

  dpy = XkbOpenDisplay (NULL, &event, &error, &major, &minor, &reason);
  assert (dpy);

  max = MAX_COMPONENTS;
  comps = XkbListComponents (dpy, XkbUseCoreKbd, &ptrns, &max);
  assert (comps);
/*    for (i = 0; i < comps->num_geometry; i++) */
/*    { */
/*      printf ("%s\n", comps->geometry[i].name); */
/*    } */
 

  list_rules ();

/*    xkb = XkbGetKeyboard (dpy, XkbAllComponentsMask, XkbUseCoreKbd); */
/*    xkb->names = NULL; */
/*    XkbGetNames (dpy, XkbGeometryNameMask, xkb); */
/*    printf ("%s\n", XkbAtomText (dpy, xkb->names->geometry, 3)); */
}
