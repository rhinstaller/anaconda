#ifndef H_GZFILE
#define H_GZFILE

typedef struct gzFile_s * gzFile;

gzFile gunzip_open(const char * file);
int gunzip_read(gzFile str, void * buf, int bytes);
int gunzip_close(gzFile str);

#endif
