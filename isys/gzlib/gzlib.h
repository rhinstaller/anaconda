#ifndef H_GZFILE
#define H_GZFILE

typedef struct gzFile_s * gzFile;

gzFile gunzip_open(const char * file);
gzFile gunzip_dopen(int fd);
gzFile gzip_open(const char * file, int mode, int perms);
gzFile gzip_dopen(int fd);
int gunzip_read(gzFile str, void * buf, int bytes);
int gzip_write(gzFile str, void * buf, int bytes);
int gunzip_close(gzFile str);
int gzip_close(gzFile str);

#endif
