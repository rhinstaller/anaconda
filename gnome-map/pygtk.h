/* -*- Mode: C; c-basic-offset: 4 -*- */
#ifndef _PYGTK_H_
#define _PYGTK_H_

#include <Python.h>
#include <gtk/gtk.h>

struct _PyGtk_FunctionStruct {
    char *pygtkVersion;
    gboolean fatalExceptions;

    void (* blockThreads)(void);
    void (* unblockThreads)(void);

    GtkDestroyNotify destroyNotify;
    GtkCallbackMarshal callbackMarshal;
    PyObject *(* argsAsTuple)(int nparams, GtkArg *args);
    int (* argsFromSequence)(GtkArg *args, int nparams, PyObject *seq);
    int (* argFromPyObject)(GtkArg *arg, PyObject *obj);
    PyObject *(* argAsPyObject)(GtkArg *arg);
    void (* retFromPyObject)(GtkArg *ret, PyObject *obj);
    PyObject *(* retAsPyObject)(GtkArg *ret);
    GtkArg *(* dictAsGtkArgs)(PyObject *dict, GtkType type, gint *nargs);
    void (* registerBoxed)(GtkType boxed_type,
			   PyObject *(*from_func)(gpointer boxed),
			   int (*to_func)(gpointer *boxed, PyObject *obj));

    gint (* enum_get_value)(GtkType enum_type, PyObject *obj, int *val);
    gint (* flag_get_value)(GtkType enum_type, PyObject *obj, int *val);

    PyTypeObject *gtk_type;
    PyObject *(* gtk_new)(GtkObject *obj);

    PyTypeObject *gtkAccelGroup_type;
    PyObject *(*gtkAccelGroup_new)(GtkAccelGroup *ag);

    PyTypeObject *gtkStyle_type;
    PyObject *(* gtkStyle_new)(GtkStyle *style);

    PyTypeObject *gdkFont_type;
    PyObject *(* gdkFont_new)(GdkFont *font);

    PyTypeObject *gdkColor_type;
    PyObject *(* gdkColor_new)(GdkColor *colour);

    PyTypeObject *gdkEvent_type;
    PyObject *(* gdkEvent_new)(GdkEvent *event);

    PyTypeObject *gdkWindow_type;
    PyObject *(* gdkWindow_new)(GdkWindow *win);

    PyTypeObject *gdkGC_type;
    PyObject *(* gdkGC_new)(GdkGC *gc);

    PyTypeObject *gdkColormap_type;
    PyObject *(* gdkColormap_new)(GdkColormap *colourmap);

    PyTypeObject *gdkDragContext_type;
    PyObject *(* gdkDragContext_new)(GdkDragContext *ctx);

    PyTypeObject *gtkSelectionData_type;
    PyObject *(* gtkSelectionData_new)(GtkSelectionData *data);

    PyTypeObject *gdkAtom_type;
    PyObject *(* gdkAtom_new)(GdkAtom atom);

    PyTypeObject *gdkCursor_type;
    PyObject *(* gdkCursor_new)(GdkCursor *cursor);

    PyTypeObject *gtkCTreeNode_type;
    PyObject *(* gtkCTreeNode_new)(GtkCTreeNode *node);
};

/* structure definitions for the various object types in PyGTK */
typedef struct {
  PyObject_HEAD
  GtkObject *obj;
} PyGtk_Object;

typedef struct {
    PyObject_HEAD
    GtkAccelGroup *obj;
} PyGtkAccelGroup_Object;

typedef struct {
    PyObject_HEAD
    GtkStyle *obj;
} PyGtkStyle_Object;

typedef struct {
    PyObject_HEAD
    GdkFont *obj;
} PyGdkFont_Object;

typedef struct {
    PyObject_HEAD
    GdkColor obj;
} PyGdkColor_Object;

typedef struct {
    PyObject_HEAD
    GdkEvent *obj;
    PyObject *attrs;
} PyGdkEvent_Object;

typedef struct {
    PyObject_HEAD
    GdkWindow *obj;
} PyGdkWindow_Object;

typedef struct {
    PyObject_HEAD
    GdkGC *obj;
} PyGdkGC_Object;

typedef struct {
    PyObject_HEAD
    GdkColormap *obj;
} PyGdkColormap_Object;

typedef struct {
    PyObject_HEAD
    GdkDragContext *obj;
} PyGdkDragContext_Object;

typedef struct {
    PyObject_HEAD
    GtkSelectionData *obj;
} PyGtkSelectionData_Object;

typedef struct {
    PyObject_HEAD
    gchar *name;
    GdkAtom atom;
} PyGdkAtom_Object;

typedef struct {
    PyObject_HEAD
    GdkCursor *obj;
} PyGdkCursor_Object;

typedef struct {
    PyObject_HEAD
    GtkCTreeNode *node;
} PyGtkCTreeNode_Object;

/* routines to get the C object value out of the PyObject wrapper */
#define PyGtk_Get(v) (((PyGtk_Object *)(v))->obj)
#define PyGtkAccelGroup_Get(v) (((PyGtkAccelGroup_Object *)(v))->obj)
#define PyGtkStyle_Get(v) (((PyGtkStyle_Object *)(v))->obj)
#define PyGdkFont_Get(v) (((PyGdkFont_Object *)(v))->obj)
#define PyGdkColor_Get(v) (&((PyGdkColor_Object *)(v))->obj)
#define PyGdkEvent_Get(v) (((PyGdkEvent_Object *)(v))->obj)
#define PyGdkWindow_Get(v) (((PyGdkWindow_Object *)(v))->obj)
#define PyGdkGC_Get(v) (((PyGdkGC_Object *)(v))->obj)
#define PyGdkColormap_Get(v) (((PyGdkColormap_Object *)(v))->obj)
#define PyGdkDragContext_Get(v) (((PyGdkDragContext_Object *)(v))->obj)
#define PyGtkSelectionData_Get(v) (((PyGtkSelectionData_Object *)(v))->obj)
#define PyGdkAtom_Get(v) (((PyGdkAtom_Object *)(v))->atom)
#define PyGdkCursor_Get(v) (((PyGdkCursor_Object *)(v))->obj)
#define PyGtkCTreeNode_Get(v) (((PyGtkCTreeNode_Object *)(v))->node)

/* this section is dependent on whether we are being included from gtkmodule.c
 * or not.  A similar source level interface should be provided in both
 * instances. */
#ifdef _INSIDE_PYGTK_
staticforward PyTypeObject PyGtk_Type;
staticforward PyTypeObject PyGtkAccelGroup_Type;
staticforward PyTypeObject PyGtkStyle_Type;
staticforward PyTypeObject PyGdkFont_Type;
staticforward PyTypeObject PyGdkColor_Type;
staticforward PyTypeObject PyGdkEvent_Type;
staticforward PyTypeObject PyGdkWindow_Type;
staticforward PyTypeObject PyGdkGC_Type;
staticforward PyTypeObject PyGdkColormap_Type;
staticforward PyTypeObject PyGdkDragContext_Type;
staticforward PyTypeObject PyGtkSelectionData_Type;
staticforward PyTypeObject PyGdkAtom_Type;
staticforward PyTypeObject PyGdkCursor_Type;
staticforward PyTypeObject PyGtkCTreeNode_Type;

/* check the type of a PyObject */
#define PyGtk_Check(v) ((v)->ob_type == &PyGtk_Type)
#define PyGtkAccelGroup_Check(v) ((v)->ob_type == &PyGtkAccelGroup_Type)
#define PyGtkStyle_Check(v) ((v)->ob_type == &PyGtkStyle_Type)
#define PyGdkFont_Check(v) ((v)->ob_type == &PyGdkFont_Type)
#define PyGdkColor_Check(v) ((v)->ob_type == &PyGdkColor_Type)
#define PyGdkEvent_Check(v) ((v)->ob_type == &PyGdkEvent_Type)
#define PyGdkWindow_Check(v) ((v)->ob_type == &PyGdkWindow_Type)
#define PyGdkGC_Check(v) ((v)->ob_type == &PyGdkGC_Type)
#define PyGdkColormap_Check(v) ((v)->ob_type == &PyGdkColormap_Type)
#define PyGdkDragContext_Check(v) ((v)->ob_type == &PyGdkDragContext_Type)
#define PyGtkSelectionData_Check(v) ((v)->ob_type == &PyGtkSelectionData_Type)
#define PyGdkAtom_Check(v) ((v)->ob_type == &PyGdkAtom_Type)
#define PyGdkCursor_Check(v) ((v)->ob_type == &PyGdkCursor_Type)
#define PyGtkCTreeNode_Check(v) ((v)->ob_type == &PyGtkCTreeNode_Type)

/* constructors for PyObject wrappers ... */
static PyObject *PyGtk_New(GtkObject *obj);
static PyObject *PyGtkAccelGroup_New(GtkAccelGroup *obj);
static PyObject *PyGtkStyle_New(GtkStyle *style);
static PyObject *PyGdkFont_New(GdkFont *font);
static PyObject *PyGdkColor_New(GdkColor *colour);
static PyObject *PyGdkEvent_New(GdkEvent *event);
static PyObject *PyGdkWindow_New(GdkWindow *window);
static PyObject *PyGdkGC_New(GdkGC *gc);
static PyObject *PyGdkColormap_New(GdkColormap *colourmap);
static PyObject *PyGdkDragContext_New(GdkDragContext *ctx);
static PyObject *PyGtkSelectionData_New(GtkSelectionData *data);
static PyObject *PyGdkAtom_New(GdkAtom atom);
static PyObject *PyGdkCursor_New(GdkCursor *cursor);
static PyObject *PyGtkCTreeNode_New(GtkCTreeNode *node);

/* miscelaneous functions */
static void PyGtk_BlockThreads(void);
static void PyGtk_UnblockThreads(void);
static void PyGtk_DestroyNotify(gpointer data);
static void PyGtk_CallbackMarshal(GtkObject *o, gpointer d, guint nargs,
				  GtkArg *args);
static PyObject *GtkArgs_AsTuple(int nparams, GtkArg *args);
static int GtkArgs_FromSequence(GtkArg *args, int nparams, PyObject *seq);
static int GtkArg_FromPyObject(GtkArg *arg, PyObject *obj);
static PyObject *GtkArg_AsPyObject(GtkArg *arg);
static void GtkRet_FromPyObject(GtkArg *ret, PyObject *py_ret);
static PyObject *GtkRet_AsPyObject(GtkArg *arg);
static GtkArg *PyDict_AsGtkArgs(PyObject *dict, GtkType type, gint *nargs);

static void PyGtk_RegisterBoxed(GtkType boxed_type,
				PyObject *(*fromarg)(gpointer boxed),
				int (*toarg)(gpointer *boxed, PyObject *obj));
gint PyGtkEnum_get_value(GtkType enum_type, PyObject *obj, int *val);
gint PyGtkFlag_get_value(GtkType enum_type, PyObject *obj, int *val);

static gboolean PyGtk_FatalExceptions = FALSE;

#else

/* for multi file extensions, define one of these in all but the main file
 * of the module */
#if defined(NO_IMPORT) || defined(NO_IMPORT_PYGTK)
extern struct _PyGtk_FunctionStruct *_PyGtk_API;
#else
struct _PyGtk_FunctionStruct *_PyGtk_API;
#endif

/* type objects */
#define PyGtk_Type              *(_PyGtk_API->gtk_type)
#define PyGtkAccelGroup_Type    *(_PyGtk_API->gtkAccelGroup_type)
#define PyGtkStyle_Type         *(_PyGtk_API->gtkStyle_type)
#define PyGdkFont_Type          *(_PyGtk_API->gdkFont_type)
#define PyGdkColor_Type         *(_PyGtk_API->gdkColor_type)
#define PyGdkEvent_Type         *(_PyGtk_API->gdkEvent_type)
#define PyGdkWindow_Type        *(_PyGtk_API->gdkWindow_type)
#define PyGdkGC_Type            *(_PyGtk_API->gdkGC_type)
#define PyGdkColormap_Type      *(_PyGtk_API->gdkColormap_type)
#define PyGdkDragContext_Type   *(_PyGtk_API->gdkDragContext_type)
#define PyGtkSelectionData_Type *(_PyGtk_API->gtkSelectionData_type)
#define PyGdkAtom_Type          *(_PyGtk_API->gdkAtom_type)
#define PyGdkCursor_Type        *(_PyGtk_API->gdkCursor_type)
#define PyGtkCTreeNode_Type     *(_PyGtk_API->gtkCTreeNode_type)

/* type checking routines */
#define PyGtk_Check(v) ((v)->ob_type == _PyGtk_API->gtk_type)
#define PyGtkAccelGroup_Check(v) ((v)->ob_type == _PyGtk_API->gtkAccelGroup_type)
#define PyGtkStyle_Check(v) ((v)->ob_type == _PyGtk_API->gtkStyle_type)
#define PyGdkFont_Check(v) ((v)->ob_type == _PyGtk_API->gdkFont_type)
#define PyGdkColor_Check(v) ((v)->ob_type == _PyGtk_API->gdkColor_type)
#define PyGdkEvent_Check(v) ((v)->ob_type == _PyGtk_API->gdkEvent_type)
#define PyGdkWindow_Check(v) ((v)->ob_type == _PyGtk_API->gdkWindow_type)
#define PyGdkGC_Check(v) ((v)->ob_type == _PyGtk_API->gdkGC_type)
#define PyGdkColormap_Check(v) ((v)->ob_type == _PyGtk_API->gdkColormap_type)
#define PyGdkDragContext_Check(v) ((v)->ob_type == _PyGtk_API->gdkDragContext_type)
#define PyGtkSelectionData_Check(v) ((v)->ob_type == _PyGtk_API->gtkSelectionData_type)
#define PyGdkAtom_Check(v) ((v)->ob_type == _PyGtk_API->gdkAtom_type)
#define PyGdkCursor_Check(v) ((v)->ob_type == _PyGtk_API->gdkCursor_type)
#define PyGtkCTreeNode_Check(v) ((v)->ob_type == _PyGtk_API->GtkCTreeNode_type)

/* type objects */
#define PyGtk_New              (_PyGtk_API->gtk_new)
#define PyGtkAccelGroup_New    (_PyGtk_API->gtkAccelGroup_new)
#define PyGtkStyle_New         (_PyGtk_API->gtkStyle_new)
#define PyGdkFont_New          (_PyGtk_API->gdkFont_new)
#define PyGdkColor_New         (_PyGtk_API->gdkColor_new)
#define PyGdkEvent_New         (_PyGtk_API->gdkEvent_new)
#define PyGdkWindow_New        (_PyGtk_API->gdkWindow_new)
#define PyGdkGC_New            (_PyGtk_API->gdkGC_new)
#define PyGdkColormap_New      (_PyGtk_API->gdkColormap_new)
#define PyGdkDragContext_New   (_PyGtk_API->gdkDragContext_new)
#define PyGtkSelectionData_New (_PyGtk_API->gtkSelectionData_new)
#define PyGdkAtom_New          (_PyGtk_API->gdkAtom_new)
#define PyGdkCursor_New        (_PyGtk_API->gdkCursor_new)
#define PyGtkCTreeNode_New     (_PyGtk_API->gtkCTreeNode_new)

/* miscelaneous other functions */
#define PyGtk_BlockThreads (_PyGtk_API->blockThreads)
#define PyGtk_UnblockThreads (_PyGtk_API->unblockThreads)
#define PyGtk_DestroyNotify (_PyGtk_API->destroyNotify)
#define PyGtk_CallbackMarshal (_PyGtk_API->callbackMarshal)
#define GtkArgs_AsTuple (_PyGtk_API->argsAsTuple)
#define GtkArgs_FromSequence (_PyGtk_API->argsFromSequence)
#define GtkArg_FromPyObject (_PyGtk_API->argFromPyObject)
#define GtkArg_AsPyObject (_PyGtk_API->argAsPyObject)
#define GtkRet_FromPyObject (_PyGtk_API->retFromPyObject)
#define GtkRet_AsPyObject (_PyGtk_API->retAsPyObject)
#define PyDict_AsGtkArgs (_PyGtk_API->dictAsGtkArgs)
#define PyGtk_RegisterBoxed (_PyGtk_API->registerBoxed)
#define PyGtkEnum_get_value (_PyGtk_API->enum_get_value)
#define PyGtkFlag_get_value (_PyGtk_API->flag_get_value)

/* some variables */
#define PyGtk_FatalExceptions (_PyGtk_API->fatalExceptions)
#define PYGTK_VERSION (_PyGtk_API->pygtkVersion)

/* a function to initialise the pygtk functions */
#define init_pygtk() { \
    PyObject *pygtk = PyImport_ImportModule("_gtk"); \
    if (pygtk != NULL) { \
	PyObject *module_dict = PyModule_GetDict(pygtk); \
	PyObject *cobject = PyDict_GetItemString(module_dict, "_PyGtk_API"); \
	if (PyCObject_Check(cobject)) \
	    _PyGtk_API = PyCObject_AsVoidPtr(cobject); \
	else { \
	    Py_FatalError("could not find _PyGtk_API object"); \
	    return; \
	} \
    } else { \
	Py_FatalError("could not import _gtk"); \
	return; \
    } \
}

#endif

#endif /* !_PYGTK_H_ */
