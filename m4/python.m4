dnl This file is based on acinclude.m4 from gnome-python-2.20.0.

dnl this one is commonly used with AM_PATH_PYTHONDIR ...
dnl AM_CHECK_PYMOD(MODNAME [,SYMBOL [,ACTION-IF-FOUND [,ACTION-IF-NOT-FOUND]]])
dnl Check if a module containing a given symbol is visible to python.
AC_DEFUN([AM_CHECK_PYMOD],
[AC_REQUIRE([AM_PATH_PYTHON])
py_mod_var=`echo $1['_']$2 | sed 'y%./+-%__p_%'`
AC_MSG_CHECKING(for ifelse([$2],[],,[$2 in ])python module $1)
AC_CACHE_VAL(py_cv_mod_$py_mod_var, [
ifelse([$2],[], [prog="
import sys
try:
        import $1
except ImportError:
        sys.exit(1)
except:
        sys.exit(0)
sys.exit(0)"], [prog="
import $1
$1.$2"])
if $PYTHON -c "$prog" 1>&AC_FD_CC 2>&AC_FD_CC
  then
    eval "py_cv_mod_$py_mod_var=yes"
  else
    eval "py_cv_mod_$py_mod_var=no"
  fi
])
py_val=`eval "echo \`echo '$py_cv_mod_'$py_mod_var\`"`
if test "x$py_val" != xno; then
  AC_MSG_RESULT(yes)
  ifelse([$3], [],, [$3
])dnl
else
  AC_MSG_RESULT(no)
  ifelse([$4], [],, [$4
])dnl
fi
])

dnl a macro to check for ability to create python extensions
dnl  AM_CHECK_PYTHON_HEADERS([ACTION-IF-POSSIBLE], [ACTION-IF-NOT-POSSIBLE])
dnl function also defines PYTHON_INCLUDES
AC_DEFUN([AM_CHECK_PYTHON_HEADERS],
[AC_REQUIRE([AM_PATH_PYTHON])

AC_SUBST(PYTHON_INCLUDES)
AC_SUBST(PYTHON_LIBS)
AC_SUBST(PYTHON_EMBED_LIBS)
AC_SUBST(PYTHON_LDFLAGS)

AC_MSG_CHECKING(for headers required to compile python extensions)
dnl deduce PYTHON_INCLUDES
py_prefix=`$PYTHON -c "import sys; print sys.prefix"`
py_exec_prefix=`$PYTHON -c "import sys; print sys.exec_prefix"`
if test -x "$PYTHON-config"; then
  PYTHON_INCLUDES=`$PYTHON-config --includes 2>/dev/null`
else
  PYTHON_INCLUDES="-I${py_prefix}/include/python${PYTHON_VERSION}"
  if test "$py_prefix" != "$py_exec_prefix"; then
    PYTHON_INCLUDES="$PYTHON_INCLUDES -I${py_exec_prefix}/include/python${PYTHON_VERSION}"
  fi
fi
dnl check if the headers exist:
save_CPPFLAGS="$CPPFLAGS"
CPPFLAGS="$CPPFLAGS $PYTHON_INCLUDES"
AC_TRY_CPP([#include <Python.h>],dnl
[AC_MSG_RESULT(found)

AC_MSG_CHECKING(for python libraries)

dnl Check whether python was compiled as shared library
link_pymodules_libpython=false;
if egrep "^#define Py_ENABLE_SHARED" "${py_exec_prefix}/include/python${PYTHON_VERSION}/pyconfig.h" > /dev/null ; then
  if test x`uname -s` != xDarwin; then
      PYTHON_LDFLAGS="-no-undefined"
      link_pymodules_libpython=true;
  fi
fi

dnl use distutils to get some python configuration variables..
PYTHON_LIB_DEPS=`$PYTHON -c "from distutils import sysconfig; print sysconfig.get_config_var('SYSLIBS'), sysconfig.get_config_var('SHLIBS')"`
PYTHON_LIBDIR=`$PYTHON -c "from distutils import sysconfig; print sysconfig.get_config_var('LIBDIR')"`
PYTHON_LIBPL=`$PYTHON -c "from distutils import sysconfig; print sysconfig.get_config_var('LIBPL')"`

save_LIBS="$LIBS"

PYTHON_EMBED_LIBS="-L${PYTHON_LIBDIR} ${PYTHON_LIB_DEPS} -lpython${PYTHON_VERSION}"

LIBS="$LIBS $PYTHON_EMBED_LIBS"
AC_TRY_LINK_FUNC(Py_Initialize, dnl
         [
            LIBS="$save_LIBS";
            if $link_pymodules_libpython; then
                PYTHON_LIBS="$PYTHON_EMBED_LIBS";
            fi
            AC_MSG_RESULT([$PYTHON_EMBED_LIBS]);
            $1], dnl
[

  PYTHON_EMBED_LIBS="-L${PYTHON_LIBPL} ${PYTHON_LIB_DEPS} -lpython${PYTHON_VERSION}"

  LIBS="$save_LIBS $PYTHON_EMBED_LIBS";
  AC_TRY_LINK_FUNC(Py_Initialize, dnl
         [
            LIBS="$save_LIBS";
            if $link_pymodules_libpython; then
                PYTHON_LIBS="$PYTHON_EMBED_LIBS";
            fi
            AC_MSG_RESULT([$PYTHON_EMBED_LIBS]);
            $1], dnl
         AC_MSG_RESULT(not found); $2)
])

$1],dnl
[AC_MSG_RESULT(not found)
$2])
CPPFLAGS="$save_CPPFLAGS"
])
