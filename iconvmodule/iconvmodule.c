#include <iconv.h>
#include <Python.h>

typedef struct {
    PyObject_HEAD
    iconv_t handle;
} IconvObject;

static PyObject *error;

staticforward PyTypeObject Iconv_Type;

static char iconv_open__doc__[]=
"open(tocode, fromcode) -> iconv handle\n"
"allocate descriptor for character set conversion";

static PyObject*
py_iconv_open(PyObject* unused, PyObject* args)
{
    char *tocode, *fromcode;
    iconv_t result;
    IconvObject *self;
    
    if (!PyArg_ParseTuple(args, "ss", &tocode, &fromcode))
	return NULL;
    
    result = iconv_open(tocode, fromcode);
    if (result == (iconv_t)(-1)) {
	PyErr_SetFromErrno(PyExc_ValueError);
	return NULL;
    }
    self = PyObject_New(IconvObject, &Iconv_Type);
    if (self == NULL) {
	iconv_close(result);
	return NULL;
    }
    self->handle = result;
    return (PyObject*) self;
}

static void
Iconv_dealloc(IconvObject *self)
{
    iconv_close(self->handle);
    PyObject_Del(self);
}

static PyObject*
Iconv_iconv(IconvObject *self, PyObject *args, PyObject* kwargs)
{
    PyObject *inbuf_obj;
    const char *inbuf, *inptr;
    char *outbuf, *outptr;
    size_t inleft, outleft, result;
    PyObject *ret;
    static char *kwarg_names[] = { "in", NULL };
    
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O:iconv", kwarg_names,
				     &inbuf_obj))
	return NULL;
    
    if (inbuf_obj->ob_type->tp_as_buffer) {
	if (PyObject_AsReadBuffer(inbuf_obj, (const void**) &inbuf, 
				  &inleft) == -1)
	    return NULL;
	inptr = inbuf;
    } else {
	PyErr_SetString(PyExc_TypeError, 
			"iconv expects string as first argument");
	return NULL;
    }

    /* begin with the same amount of space as the input */
    outptr = outbuf = malloc(inleft);
    outleft = inleft;

    /* Perform the conversion. */
    do {
	result = iconv(self->handle,
		       (char **) &inptr, &inleft, &outptr, &outleft);
	if (result == (size_t) -1) {
	    if (errno == E2BIG) {
		/* we ran out of space in outbuf, it needs to be bigger */
		char *newbuf;
		/* a guess at how much more we need */
		size_t cursize, curpos, extra = inleft * 2;

		/* calculate the current position in the output buffer
		   so we can move outptr to the correct place in the realloced
		   space */
		cursize = outptr - outbuf + outleft;
		curpos = outptr - outbuf;
		newbuf = realloc(outbuf, cursize + extra);
		if (newbuf == NULL) {
		    free(outbuf);
		    /* XXX set exception */
		    return NULL;
		}
		outbuf = newbuf;
		outptr = outbuf + curpos;
		
		/* now we have more space to convert into */
		outleft += extra;
	    } else {
		/* if we managed to convert everything up to the last byte,
		   it was probably a NULL terminated string (you can't convert
		   the NULL) */
		if (inleft == 0)
		    break;
		PyErr_SetFromErrno(PyExc_SystemError);
		free(outbuf);
		return NULL;
	    }
	}
    } while (inleft > 0);

    /* create a new string object from the converted buffer */
    ret = PyString_FromStringAndSize(outbuf, outptr - outbuf);
    free(outbuf);

    return ret;
}

static char Iconv_iconv__doc__[] =
"iconv(in) -> out\n"
"Convert in to out.";


static PyMethodDef Iconv_methods[] = {
	{ "iconv",	(PyCFunction)Iconv_iconv,	
	  METH_KEYWORDS | METH_VARARGS,	Iconv_iconv__doc__},
	{ NULL,		NULL }
};

static PyObject *
Iconv_getattr(PyObject *self, char *name)
{
    return Py_FindMethod(Iconv_methods, self, name);
}

statichere PyTypeObject Iconv_Type = {
    PyObject_HEAD_INIT(NULL)
    0,			/*ob_size*/
    "Iconv",		/*tp_name*/
    sizeof(IconvObject),	/*tp_basicsize*/
    0,			/*tp_itemsize*/
    /* methods */
    (destructor)Iconv_dealloc, /*tp_dealloc*/
    0,			/*tp_print*/
    (getattrfunc)Iconv_getattr, /*tp_getattr*/
    0,			/*tp_setattr*/
    0,			/*tp_compare*/
    0,			/*tp_repr*/
    0,			/*tp_as_number*/
    0,			/*tp_as_sequence*/
    0,			/*tp_as_mapping*/
    0,			/*tp_hash*/
};

static PyMethodDef iconv_methods[] = {
    { "open",		py_iconv_open,
      METH_VARARGS,	iconv_open__doc__},
    { NULL,		NULL}		/* sentinel */
};

static char __doc__[] =
"The iconv module provides an interface to the iconv library.";

DL_EXPORT(void)
initiconv(void)
{
    PyObject *m, *d;

    Iconv_Type.ob_type = &PyType_Type;
    
    /* Create the module and add the functions */
    m = Py_InitModule4("iconv", iconv_methods, __doc__, 
		       NULL, PYTHON_API_VERSION);

    /* Add some symbolic constants to the module */
    d = PyModule_GetDict(m);
    error = PyErr_NewException("iconv.error", PyExc_ValueError, NULL);
    PyDict_SetItemString(d, "error", error);
}
