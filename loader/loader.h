#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1

#define LOADER_FLAGS_TESTING		(1 << 0)
#define LOADER_FLAGS_EXPERT		(1 << 1)
#define LOADER_FLAGS_TEXT		(1 << 2)
#define LOADER_FLAGS_RESCUE		(1 << 3)
#define LOADER_FLAGS_KICKSTART		(1 << 4)
#define LOADER_FLAGS_KSFLOPPY		(1 << 5)
#define LOADER_FLAGS_KSHD		(1 << 6)
#define LOADER_FLAGS_NOPROBE		(1 << 7)
#define LOADER_FLAGS_MODDISK		(1 << 8)

#define FL_TESTING(a)	    ((a) & LOADER_FLAGS_TESTING)
#define FL_EXPERT(a)	    ((a) & LOADER_FLAGS_EXPERT)
#define FL_TEXT(a)	    ((a) & LOADER_FLAGS_TEXT)
#define FL_RESCUE(a)	    ((a) & LOADER_FLAGS_RESCUE)
#define FL_KICKSTART(a)	    ((a) & LOADER_FLAGS_KICKSTART)
#define FL_KSFLOPPY(a)	    ((a) & LOADER_FLAGS_KSFLOPPY)
#define FL_KSHD(a)	    ((a) & LOADER_FLAGS_KSHD)
#define FL_NOPROBE(a)	    ((a) & LOADER_FLAGS_NOPROBE)
#define FL_MODDISK(a)	    ((a) & LOADER_FLAGS_MODDISK)

