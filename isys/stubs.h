/* we use gzlib when linked against dietlibc, but otherwise, we should use
   zlib.  it would make more sense to do the defines in the other direction, 
   but that causes symbol wackiness because both gunzip_open and gzip_open in
   gzlib are gzopen from zlib
*/

#ifndef ISYS_STUB
#define ISYS_STUB

#ifndef GZLIB
#include <zlib.h>

#define gunzip_open(x) gzopen(x, "r")
#define gunzip_dopen gzdopen(x, "r")
#define gunzip_close gzclose
#define gunzip_read gzread
#define gzip_write gzwrite
#define gzip_open(x, y, z) gzopen(x, "w")

#else
#include "gzlib/gzlib.h"

#endif

#endif
