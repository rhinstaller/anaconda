#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "Python.h"
#include "rpmlib.h"

/* Forward types */

typedef struct rpmdbObject_s rpmdbObject;
typedef struct hdrObject_s hdrObject;

/* Prototypes */

static void rpmdbDealloc(rpmdbObject * s);
static PyObject * rpmdbGetAttr(rpmdbObject * s, char * name);
static PyObject * rpmdbFirst(rpmdbObject * s, PyObject * args);
static PyObject * rpmdbNext(rpmdbObject * s, PyObject * args);
static int rpmdbLength(rpmdbObject * s);
static hdrObject * rpmdbSubscript(rpmdbObject * s, PyObject * key);

static void hdrDealloc(hdrObject * s);
static PyObject * hdrGetAttr(hdrObject * s, char * name);
static PyObject * hdrSubscript(hdrObject * s, int item);
static PyObject * hdrVerifyFile(hdrObject * s, PyObject * args);

void initrpm(void);
static rpmdbObject * rpmOpenDB(PyObject * self, PyObject * args);
static PyObject * rpmHeaderFromPackage(PyObject * self, PyObject * args);
static PyObject * rpmHeaderFromList(PyObject * self, PyObject * args);

/* Types */

static PyMethodDef rpmModuleMethods[] = {
    { "opendb", (PyCFunction) rpmOpenDB, METH_VARARGS, NULL },
    { "headerFromPackage", (PyCFunction) rpmHeaderFromPackage, METH_VARARGS, NULL },
    { "readHeaderList", (PyCFunction) rpmHeaderFromList, METH_VARARGS, NULL },
    { NULL }
} ;

struct rpmdbObject_s {
    PyObject_HEAD;
    rpmdb db;
} ;

struct hdrObject_s {
    PyObject_HEAD;
    Header h;
    char ** md5list;
    char ** fileList;
    char ** linkList;
    int_32 * fileSizes;
    int_32 * mtimes;
    int_32 * uids, * gids;
    unsigned short * rdevs;
    unsigned short * modes;
} ;

/* Data */

static PyObject * pyrpmError;

static PySequenceMethods hdrAsSequence = {
	0,				/* length */
	0,				/* concat */
	0,				/* repeat */
	hdrSubscript,			/* item */
	0,				/* slice */
	0,				/* assign item */
	0,				/* assign slice */
};

static PyTypeObject hdrType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,				/* ob_size */
	"header",			/* tp_name */
	sizeof(hdrObject),		/* tp_size */
	0,				/* tp_itemsize */
	(destructor) hdrDealloc, 	/* tp_dealloc */
	0,				/* tp_print */
	(getattrfunc) hdrGetAttr, 	/* tp_getattr */
	0,				/* tp_setattr */
	0,				/* tp_compare */
	0,				/* tp_repr */
	0,				/* tp_as_number */
	&hdrAsSequence,			/* tp_as_sequence */
	0,				/* tp_as_mapping */
};

static PyMappingMethods rpmdbAsMapping = {
	(inquiry) rpmdbLength,		/* mp_length */
	(binaryfunc) rpmdbSubscript,	/* mp_subscript */
	(objobjargproc)0,		/* mp_ass_subscript */
};

static PyTypeObject rpmdbType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,				/* ob_size */
	"rpmdb",			/* tp_name */
	sizeof(rpmdbObject),		/* tp_size */
	0,				/* tp_itemsize */
	(destructor) rpmdbDealloc, 	/* tp_dealloc */
	0,				/* tp_print */
	(getattrfunc) rpmdbGetAttr, 	/* tp_getattr */
	0,				/* tp_setattr */
	0,				/* tp_compare */
	0,				/* tp_repr */
	0,				/* tp_as_number */
	0,				/* tp_as_sequence */
	&rpmdbAsMapping,		/* tp_as_mapping */
};

static struct PyMethodDef rpmdbMethods[] = {
	{"firstkey",	(PyCFunction) rpmdbFirst },
	{"nextkey",	(PyCFunction) rpmdbNext },
	{NULL,		NULL}		/* sentinel */
};

static struct PyMethodDef hdrMethods[] = {
	{"verifyFile",	(PyCFunction) hdrVerifyFile },
	{NULL,		NULL}		/* sentinel */
};

/* Code */

void initrpm(void) {
    PyObject * m, * d, * tag;
    int i;

    rpmReadConfigFiles(NULL, NULL);

    m = Py_InitModule("rpm", rpmModuleMethods);
    d = PyModule_GetDict(m);

    pyrpmError = PyString_FromString("rpm.error");
    PyDict_SetItemString(d, "error", pyrpmError);

    for (i = 0; i < rpmTagTableSize; i++) {
	tag = PyInt_FromLong(rpmTagTable[i].val);
	PyDict_SetItemString(d, rpmTagTable[i].name, tag);
    }

    PyDict_SetItemString(d, "RPMFILE_STATE_NORMAL", 
			 PyInt_FromLong(RPMFILE_STATE_NORMAL));
    PyDict_SetItemString(d, "RPMFILE_STATE_REPLACED", 
			 PyInt_FromLong(RPMFILE_STATE_REPLACED));
    PyDict_SetItemString(d, "RPMFILE_STATE_NOTINSTALLED", 
			 PyInt_FromLong(RPMFILE_STATE_NOTINSTALLED));
    PyDict_SetItemString(d, "RPMFILE_CONFIG", 
			 PyInt_FromLong(RPMFILE_CONFIG));
    PyDict_SetItemString(d, "RPMFILE_DOC", 
			 PyInt_FromLong(RPMFILE_DOC));
}

static rpmdbObject * rpmOpenDB(PyObject * self, PyObject * args) {
    rpmdbObject * o;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    o = PyObject_NEW(rpmdbObject, &rpmdbType);
    o->db = NULL;
    if (rpmdbOpen("", &o->db, O_RDONLY, 0)) {
	Py_DECREF(o);
	PyErr_SetString(pyrpmError, "cannot open database in /var/lib/rpm");
	return NULL;
    }

    return o;
}

static PyObject * rpmHeaderFromList(PyObject * self, PyObject * args) {
    char * filespec;
    FD_t fd;
    Header header;
    PyObject * list;
    hdrObject * h;

    if (!PyArg_ParseTuple(args, "s", &filespec)) return NULL;
    fd = fdOpen(filespec, O_RDONLY, 0);

    if (!fd) {
	PyErr_SetFromErrno(pyrpmError);
	return NULL;
    }

    list = PyList_New(0);

    header = headerRead(fd, HEADER_MAGIC_YES);
    while (header) {
	h = (hdrObject *) PyObject_NEW(PyObject, &hdrType);
	h->h = header;
	h->fileList = h->linkList = h->md5list = NULL;
	h->uids = h->gids = h->mtimes = h->fileSizes = NULL;
	h->modes = h->rdevs = NULL;
	if (PyList_Append(list, (PyObject *) h)) {
	    Py_DECREF(list);
	    Py_DECREF(h);
	    return NULL;
	}

	Py_DECREF(h);

	header = headerRead(fd, HEADER_MAGIC_YES);
    }

    fdClose(fd);

    return list;
}

static PyObject * rpmHeaderFromPackage(PyObject * self, PyObject * args) {
    char * filespec;
    hdrObject * h;
    Header header;
    int rc;
    FD_t fd;
    int isSource;

    if (!PyArg_ParseTuple(args, "s", &filespec)) return NULL;
    fd = fdOpen(filespec, O_RDONLY, 0);

    if (!fd) {
	if (errno == EISDIR) {
	    Py_INCREF(Py_None);
	    return (PyObject *) Py_None;
	} else {
	    PyErr_SetFromErrno(pyrpmError);
	    return NULL;
	}
    } else {
	rc = rpmReadPackageHeader(fd, &header, &isSource, NULL, NULL);
	fdClose(fd);

	switch (rc) {
	  case 0:
	    h = (hdrObject *) PyObject_NEW(PyObject, &hdrType);
	    h->h = header;
	    h->fileList = h->linkList = h->md5list = NULL;
	    h->uids = h->gids = h->mtimes = h->fileSizes = NULL;
	    h->modes = h->rdevs = NULL;
	    break;

	  case 1:
	    Py_INCREF(Py_None);
	    h = (hdrObject *) Py_None;
	    break;

	  default:
	    PyErr_SetString(pyrpmError, "error reading package");
	    return NULL;
	}
    }

    return Py_BuildValue("(Oi)", h, isSource);
}

/* methods for rpmdb object */

static PyObject * rpmdbGetAttr(rpmdbObject * s, char * name) {
    return Py_FindMethod(rpmdbMethods, (PyObject * ) s, name);
}

static void rpmdbDealloc(rpmdbObject * s) {
    if (s->db) {
	rpmdbClose(s->db);
    }
}

static PyObject * rpmdbFirst(rpmdbObject * s, PyObject * args) {
    int first;

    if (!PyArg_Parse(args, "")) return NULL;

    first = rpmdbFirstRecNum(s->db);

    if (!first) {
	PyErr_SetString(pyrpmError, "cannot find first entry in database\n");
	return NULL;
    }

    return Py_BuildValue("i", first);
}

static PyObject * rpmdbNext(rpmdbObject * s, PyObject * args) {
    int where;

    if (!PyArg_Parse(args, "i", &where)) return NULL;

    where = rpmdbNextRecNum(s->db, where);

    if (!where) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    return Py_BuildValue("i", where);
}

static int rpmdbLength(rpmdbObject * s) {
    int first;
    int count = 0;

    first = rpmdbFirstRecNum(s->db);
    if (!first) return 0;

    count++;
    while ((first = rpmdbNextRecNum(s->db, first))) {
	count++;
    }

    return count;
}

static hdrObject * rpmdbSubscript(rpmdbObject * s, PyObject * key) {
    int offset;
    hdrObject * h;
    
    if (!PyInt_Check(key)) {
	PyErr_SetString(PyExc_TypeError, "integer expected");
	return NULL;
    }

    offset = (int) PyInt_AsLong(key);

    h = PyObject_NEW(hdrObject, &hdrType);
    h->h = NULL;
    h->h = rpmdbGetRecord(s->db, offset);
    h->fileList = h->linkList = h->md5list = NULL;
    h->uids = h->gids = h->mtimes = h->fileSizes = NULL;
    h->modes = h->rdevs = NULL;
    if (!h->h) {
	Py_DECREF(h);
	PyErr_SetString(pyrpmError, "cannot read rpmdb entry");
	return NULL;
    }
    
    return h;
}

/* methods for header object */

static void hdrDealloc(hdrObject * s) {
    if (s->h) headerFree(s->h);
    if (s->md5list) free(s->md5list);
    if (s->fileList) free(s->fileList);
    if (s->linkList) free(s->linkList);
}

static PyObject * hdrGetAttr(hdrObject * s, char * name) {
    return Py_FindMethod(hdrMethods, (PyObject * ) s, name);
}

static PyObject * hdrSubscript(hdrObject * s, int tag) {
    int type, count;
    void * data;
    PyObject * o, * metao;
    int i;
    char ** stringArray;
    int forceArray = 0;

    if (!headerGetEntry(s->h, tag, &type, &data, &count)) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    switch (tag) {
      case RPMTAG_FILENAMES:
      case RPMTAG_FILESIZES:
      case RPMTAG_FILESTATES:
      case RPMTAG_FILEMODES:
      case RPMTAG_FILEUIDS:
      case RPMTAG_FILEGIDS:
      case RPMTAG_FILERDEVS:
      case RPMTAG_FILEMTIMES:
      case RPMTAG_FILEMD5S:
      case RPMTAG_FILELINKTOS:
      case RPMTAG_FILEFLAGS:
      case RPMTAG_ROOT:
      case RPMTAG_FILEUSERNAME:
      case RPMTAG_FILEGROUPNAME:
	forceArray = 1;
    }

    switch (type) {
      case RPM_BIN_TYPE:
	o = PyString_FromStringAndSize(data, count);
	break;

      case RPM_INT32_TYPE:
	if (count != 1 || forceArray) {
	    metao = PyList_New(0);
	    for (i = 0; i < count; i++) {
		o = PyInt_FromLong(((int *) data)[i]);
		PyList_Append(metao, o);
		Py_DECREF(o);
	    }
	    o = metao;
	} else {
	    o = PyInt_FromLong(*((int *) data));
	}
	break;

      case RPM_CHAR_TYPE:
      case RPM_INT8_TYPE:
	if (count != 1 || forceArray) {
	    metao = PyList_New(0);
	    for (i = 0; i < count; i++) {
		o = PyInt_FromLong(((char *) data)[i]);
		PyList_Append(metao, o);
		Py_DECREF(o);
	    }
	    o = metao;
	} else {
	    o = PyInt_FromLong(*((char *) data));
	}
	break;

      case RPM_INT16_TYPE:
	if (count != 1 || forceArray) {
	    metao = PyList_New(0);
	    for (i = 0; i < count; i++) {
		o = PyInt_FromLong(((short *) data)[i]);
		PyList_Append(metao, o);
		Py_DECREF(o);
	    }
	    o = metao;
	} else {
	    o = PyInt_FromLong(*((short *) data));
	}
	break;

      case RPM_STRING_ARRAY_TYPE:
	stringArray = data;

	metao = PyList_New(0);
	for (i = 0; i < count; i++) {
	    o = PyString_FromString(stringArray[i]);
	    PyList_Append(metao, o);
	    Py_DECREF(o);
	}
	o = metao;
	break;

      case RPM_STRING_TYPE:
	if (count != 1 || forceArray) {
	    stringArray = data;
	    
	    metao = PyList_New(0);
	    for (i=0; i < count; i++) {
		o = PyString_FromString(stringArray[i]);
		PyList_Append(metao, o);
		Py_DECREF(o);
	    }
	    o = metao;
	} else
	  o = PyString_FromString(data);
	break;

      default:
	PyErr_SetString(PyExc_TypeError, "unsupported type in header");
	return NULL;
    }

    return o;
}

/* Returns a list of these tuple for each part which failed:

	(attr_name, correctValue, currentValue)

	It should be passwd the file number to verify.
*/
static PyObject * hdrVerifyFile(hdrObject * s, PyObject * args) {
    int fileNumber;
    int verifyResult;
    PyObject * list, * tuple, * attrName;
    int type, count;
    struct stat sb;
    char buf[2048];
    int i;
    time_t timeInt;
    struct tm * timeStruct;

    if (!PyInt_Check(args)) {
	PyErr_SetString(PyExc_TypeError, "integer expected");
	return NULL;
    }

    fileNumber = (int) PyInt_AsLong(args);

    if (rpmVerifyFile("", s->h, fileNumber, &verifyResult, 0)) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    list = PyList_New(0);

    if (!verifyResult) return list;

    if (!s->fileList) {
	headerGetEntry(s->h, RPMTAG_FILENAMES, &type, (void **) &s->fileList, 
		 &count);
    }

    lstat(s->fileList[fileNumber], &sb);

    if (verifyResult & RPMVERIFY_MD5) {
	if (!s->md5list) {
	    headerGetEntry(s->h, RPMTAG_FILEMD5S, &type, (void **) &s->md5list, 
		     &count);
	}
	
	if (mdfile(s->fileList[fileNumber], buf)) {
	    strcpy(buf, "(unknown)");
	} 
	
	tuple = PyTuple_New(3);
	attrName = PyString_FromString("checksum");
	PyTuple_SetItem(tuple, 0, attrName);
	PyTuple_SetItem(tuple, 1, PyString_FromString(s->md5list[fileNumber]));
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_FILESIZE) {
	if (!s->fileSizes) {
	    headerGetEntry(s->h, RPMTAG_FILESIZES, &type, (void **) &s->fileSizes, 
		     &count);

	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("size");
	PyTuple_SetItem(tuple, 0, attrName);

	sprintf(buf, "%d", 100);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));
	sprintf(buf, "%ld", sb.st_size);
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_LINKTO) {
	if (!s->linkList) {
	    headerGetEntry(s->h, RPMTAG_FILELINKTOS, &type, (void **) &s->linkList, 
		     &count);
	}

	i = readlink(s->fileList[fileNumber], buf, sizeof(buf));
	if (i <= 0)
	    strcpy(buf, "(unknown)");
	else
	    buf[i] = '\0';

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("link");
	PyTuple_SetItem(tuple, 0, attrName);
	PyTuple_SetItem(tuple, 1, PyString_FromString(s->linkList[fileNumber]));
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_MTIME) {
	if (!s->mtimes) {
	    headerGetEntry(s->h, RPMTAG_FILEMTIMES, &type, (void **) &s->mtimes, 
		     &count);
	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("time");
	PyTuple_SetItem(tuple, 0, attrName);

	timeInt = sb.st_mtime;
	timeStruct = localtime(&timeInt);
	strftime(buf, sizeof(buf) - 1, "%c", timeStruct);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));

	timeInt = s->mtimes[fileNumber];
	timeStruct = localtime(&timeInt);
	strftime(buf, sizeof(buf) - 1, "%c", timeStruct);

	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));

	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_RDEV) {
	if (!s->rdevs) {
	    headerGetEntry(s->h, RPMTAG_FILERDEVS, &type, (void **) &s->rdevs, 
		     &count);
	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("device");

	PyTuple_SetItem(tuple, 0, attrName);
	sprintf(buf, "0x%-4x", s->rdevs[fileNumber]);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));
	sprintf(buf, "0x%-4x", sb.st_rdev);
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    /* RPMVERIFY_USER and RPM_VERIFY_GROUP are handled wrong here, but rpmlib.a
       doesn't do these correctly either. At least this is consisten */
    if (verifyResult & RPMVERIFY_USER) {
	if (!s->uids) {
	    headerGetEntry(s->h, RPMTAG_FILEUIDS, &type, (void **) &s->uids, 
		     &count);
	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("uid");
	PyTuple_SetItem(tuple, 0, attrName);
	sprintf(buf, "%d", s->uids[fileNumber]);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));
	sprintf(buf, "%d", sb.st_uid);
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_GROUP) {
	if (!s->gids) {
	    headerGetEntry(s->h, RPMTAG_FILEGIDS, &type, (void **) &s->gids, 
		     &count);
	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("gid");
	PyTuple_SetItem(tuple, 0, attrName);
	sprintf(buf, "%d", s->gids[fileNumber]);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));
	sprintf(buf, "%d", sb.st_gid);
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    if (verifyResult & RPMVERIFY_MODE) {
	if (!s->modes) {
	    headerGetEntry(s->h, RPMTAG_FILEMODES, &type, (void **) &s->modes, 
		     &count);
	}

	tuple = PyTuple_New(3);
	attrName = PyString_FromString("permissions");
	PyTuple_SetItem(tuple, 0, attrName);
	sprintf(buf, "0%-4o", s->modes[fileNumber]);
	PyTuple_SetItem(tuple, 1, PyString_FromString(buf));
	sprintf(buf, "0%-4o", sb.st_mode);
	PyTuple_SetItem(tuple, 2, PyString_FromString(buf));
	PyList_Append(list, tuple);
    }

    return list;
}
