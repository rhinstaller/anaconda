#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1

#define LOADER_FLAGS_TESTING		(1 << 0)
#define LOADER_FLAGS_EXPERT		(1 << 1)
#define LOADER_FLAGS_TEXT		(1 << 2)

#define FL_TESTING(a) ((a) & LOADER_FLAGS_TESTING)
#define FL_EXPERT(a) ((a) & LOADER_FLAGS_EXPERT)
#define FL_TEXT(a) ((a) & LOADER_FLAGS_TEXT)

