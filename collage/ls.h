#ifndef H_LS
#define H_LS

#define SENDDIR_ALL		(1 << 0)
#define SENDDIR_LONG		(1 << 1)
#define SENDDIR_RECURSE		(1 << 2)
#define SENDDIR_SIMPLEDIRS	(1 << 3)
#define SENDDIR_NUMIDS		(1 << 4)
#define SENDDIR_FILETYPE	(1 << 5)
#define SENDDIR_FOLLOWLINKS	(1 << 6)
#define SENDDIR_SORTNONE	(1 << 7)
#define SENDDIR_SORTMTIME	(1 << 8)
#define SENDDIR_SORTSIZE	(1 << 9)
#define SENDDIR_SORTREVERSE	(1 << 9)
#define SENDDIR_MULTICOLUMN	(1 << 10)

char * fileStatStr(char * dir, char * fn, struct stat * sbp, int flags);
void listFiles(char * path, char * fn, int flags);

#endif
