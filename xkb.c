#include <stdio.h>
#include <fcntl.h>
#include <Python.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/extensions/XKBrules.h>
#include <gdk/gdkx.h>
#include <assert.h>

#define max(a,b) ((a) > (b) ? (a) : (b))
#define min(a,b) ((a) < (b) ? (a) : (b))

#define MAX_COMPONENTS 400
#define XKB_XFREE86_RULES "/usr/X11R6/lib/X11/xkb/rules/xfree86"
#define XKB_SUN_RULES "/usr/X11R6/lib/X11/xkb/rules/sun"

static XkbRF_RulesPtr rules;

PyObject *list_rules ();
PyObject *set_rule (PyObject *, PyObject *);
PyObject * py_get_rulesbase ();

char * get_rulesbase ();

static PyMethodDef _xkbMethods[] = {
    { "list_rules", list_rules, 1 },
    { "set_rule", set_rule, 1 },
    { "get_rulesbase", py_get_rulesbase, 1 },
    { NULL, NULL }
};

char *
get_rulesbase ()
{
  char *rulesbase = XKB_XFREE86_RULES;
#ifdef __sparc__
  int fd;
  
  fd = open("/dev/kbd", O_RDONLY);
  if (fd >= 0) {
    rulesbase = XKB_SUN_RULES;
  }
#endif

  return rulesbase;
}

PyObject *
py_get_rulesbase ()
{
  return Py_BuildValue ("s", get_rulesbase ());
}
  
void 
init_xkb ()
{
  char *lang;
  PyObject *m;
  m = Py_InitModule ("_xkb", _xkbMethods);

  lang = getenv ("LC_ALL");
  rules = XkbRF_Load (get_rulesbase (), (lang) ? lang : "C", True, True);
  if (!rules)
    Py_FatalError ("unable to load XKB rules database");

  if (PyErr_Occurred ())
    Py_FatalError ("can't initialize module _xkb");
}

PyObject *
set_rule (PyObject *self, PyObject *args)
{
  XkbRF_VarDefsRec defs;
  XkbComponentNamesRec rnames;

  if (!PyArg_ParseTuple (args, "ssss", &defs.model, &defs.layout, &defs.variant, &defs.options))
    return NULL;

  if (!strcmp (defs.model, ""))
    defs.model = NULL;
  if (!strcmp (defs.layout, ""))
    defs.layout = NULL;
  if (!strcmp (defs.variant, ""))
    defs.variant = NULL;
  if (!strcmp (defs.options, ""))
    defs.options = NULL;

  XkbRF_GetComponents (rules, &defs, &rnames);

  XkbGetKeyboardByName (GDK_DISPLAY (), XkbUseCoreKbd, &rnames, 
			XkbGBN_AllComponentsMask, 
                        XkbGBN_AllComponentsMask, True);

  XkbRF_SetNamesProp (GDK_DISPLAY (), get_rulesbase (), &defs);

  return Py_BuildValue ("i", 1);
}

PyObject * 
list_rules ()
{
  PyObject *models, *layouts, *variants, *options, *py_rules;
  int num_comp;
  int i;

  models = PyDict_New ();
  num_comp = min (rules->models.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (rules->models.desc[i].name);
      desc = PyString_FromString (rules->models.desc[i].desc);
      PyDict_SetItem (models, name, desc);
    }

  layouts = PyDict_New ();
  num_comp = min (rules->layouts.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (rules->layouts.desc[i].name);
      desc = PyString_FromString (rules->layouts.desc[i].desc);
      PyDict_SetItem (layouts, name, desc);
    }
  
  variants = PyDict_New ();
  num_comp = min (rules->variants.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (rules->variants.desc[i].name);
      desc = PyString_FromString (rules->variants.desc[i].desc);
      PyDict_SetItem (variants, name, desc);
    }

  options = PyDict_New ();
  num_comp = min (rules->options.num_desc, MAX_COMPONENTS);
  for (i = 0; i < num_comp; i++) 
    {
      PyObject *desc, *name;

      name = PyString_FromString (rules->options.desc[i].name);
      desc = PyString_FromString (rules->options.desc[i].desc);
      PyDict_SetItem (options, name, desc);
    }

  py_rules = PyTuple_New (4);

  PyTuple_SET_ITEM (py_rules, 0, models);
  PyTuple_SET_ITEM (py_rules, 1, layouts);
  PyTuple_SET_ITEM (py_rules, 2, variants);
  PyTuple_SET_ITEM (py_rules, 3, options);

  return py_rules;
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

  return 0;
}
