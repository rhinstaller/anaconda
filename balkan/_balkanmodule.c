#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "Python.h"
#include "balkan.h"

typedef struct pythonPartTable_s {
    PyObject_HEAD;
    struct partitionTable table;
} pythonPartTable;

static void emptyDestructor(PyObject * s);
static pythonPartTable * readTable(PyObject * s, PyObject * args);
static PyObject * tableGetAttr(PyObject * s, char * name);
static int tableLength(PyObject * o);
PyObject * tableItem(PyObject * o, int n);

static PySequenceMethods pythonPartTableAsSequence = {
	tableLength,			/* length */
	0,				/* concat */
	0,				/* repeat */
	tableItem,			/* item */
	0,				/* slice */
	0,				/* assign item */
	0,				/* assign slice */
};

static PyTypeObject pythonPartTableType = {
        PyObject_HEAD_INIT(&PyType_Type)
        0,                              /* ob_size */
        "parttable",                    /* tp_name */
        sizeof(pythonPartTable),        /* tp_size */
        0,                              /* tp_itemsize */
        emptyDestructor,      		/* tp_dealloc */
        0,                              /* tp_print */
        tableGetAttr,  			/* tp_getattr */
        0,                              /* tp_setattr */
        0,                              /* tp_compare */
        0,                              /* tp_repr */
        0,                              /* tp_as_number */
        &pythonPartTableAsSequence,     /* tp_as_sequence */
        0,                		/* tp_as_mapping */
};

static PyMethodDef balkanModuleMethods[] = {
    { "readTable", (PyCFunction) readTable, METH_VARARGS, NULL },
    { NULL }
} ;

static pythonPartTable * readTable(PyObject * s, PyObject * args) {
    char * device;
    pythonPartTable * table;
    int fd;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    table = PyObject_NEW(pythonPartTable, &pythonPartTableType);

    fd = open(device, O_RDONLY | O_RDONLY);
    balkanReadTable(fd, &table->table);
    close(fd);

    return table;
}

static int tableLength(PyObject * o) {
    pythonPartTable * t = (void *) o;

    return t->table.maxNumPartitions;
}

PyObject * tableItem(PyObject * o, int n) {
    pythonPartTable * t = (void *) o;

    if (n > t->table.maxNumPartitions) {
	PyErr_SetString(PyExc_IndexError, "index out of bounds");
	return NULL;
    }

    return Py_BuildValue("(iii)", t->table.parts[n].type,
			 t->table.parts[n].startSector,
			 t->table.parts[n].size);
}

static PyObject * tableGetAttr(PyObject * o, char * name) {
    pythonPartTable * t = (void *) o;

    if (!strcmp(name, "allocationUnit")) {
	return Py_BuildValue("i", t->table.allocationUnit);
    } else if (!strcmp(name, "sectorSize")) {
	return Py_BuildValue("i", t->table.sectorSize);
    }

    return NULL;
}

void init_balkan(void) {
    Py_InitModule("_balkan", balkanModuleMethods);
}

static void emptyDestructor(PyObject * s) {
}
