#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_NOOP 2
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
#define LOADER_FLAGS_ISA		(1 << 9)
#define LOADER_FLAGS_SERIAL		(1 << 10)
#define LOADER_FLAGS_UPDATES		(1 << 11)
#define LOADER_FLAGS_KSFILE		(1 << 12)
#define LOADER_FLAGS_KSCDROM		(1 << 13)
#define LOADER_FLAGS_MCHECK		(1 << 14)
#define LOADER_FLAGS_KSNFS		(1 << 15)
#define LOADER_FLAGS_NOUSB              (1 << 16)
#define LOADER_FLAGS_NOSHELL            (1 << 17)

#define FL_TESTING(a)	    ((a) & LOADER_FLAGS_TESTING)
#define FL_EXPERT(a)	    ((a) & LOADER_FLAGS_EXPERT)
#define FL_TEXT(a)	    ((a) & LOADER_FLAGS_TEXT)
#define FL_RESCUE(a)	    ((a) & LOADER_FLAGS_RESCUE)
#define FL_KICKSTART(a)	    ((a) & LOADER_FLAGS_KICKSTART)
#define FL_KSFLOPPY(a)	    ((a) & LOADER_FLAGS_KSFLOPPY)
#define FL_KSHD(a)	    ((a) & LOADER_FLAGS_KSHD)
#define FL_NOPROBE(a)	    ((a) & LOADER_FLAGS_NOPROBE)
#define FL_MODDISK(a)	    ((a) & LOADER_FLAGS_MODDISK)
#define FL_ISA(a)	    ((a) & LOADER_FLAGS_ISA)
#define FL_SERIAL(a)	    ((a) & LOADER_FLAGS_SERIAL)
#define FL_UPDATES(a)	    ((a) & LOADER_FLAGS_UPDATES)
#define FL_KSFILE(a)	    ((a) & LOADER_FLAGS_KSFILE)
#define FL_KSCDROM(a)	    ((a) & LOADER_FLAGS_KSCDROM)
#define FL_MCHECK(a)	    ((a) & LOADER_FLAGS_MCHECK)
#define FL_KSNFS(a)	    ((a) & LOADER_FLAGS_KSNFS)
#define FL_NOUSB(a)	    ((a) & LOADER_FLAGS_NOUSB)
#define FL_NOSHELL(a)	    ((a) & LOADER_FLAGS_NOSHELL)

#define CODE_PCMCIA	1

