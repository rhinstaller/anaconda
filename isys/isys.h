#ifndef H_ISYS
#define H_ISYS

#define MIN_ROOTPART_SIZE_MB	250

enum driverMajor { DRIVER_NONE = 0, DRIVER_SCSI, DRIVER_NET, DRIVER_CDROM,
		   DRIVER_PCMCIA, DRIVER_FS, DRIVER_OTHER = 1000};
enum driverMinor { DRIVER_MINOR_NONE = 0, DRIVER_MINOR_ETHERNET,
		   DRIVER_MINOR_PLIP, DRIVER_MINOR_TR };

struct moduleArg {
    char * arg;
    char * description;
};

#define MI_FLAG_NOMISCARGS	(1 << 0)

struct moduleInfo {
    char * moduleName;
    char * description;
    enum driverMajor major;
    enum driverMinor minor;
    int numArgs;
    struct moduleArg * args;
    int flags;
    void * locationID;
};

struct moduleInfoSet_s {
    struct moduleInfo * moduleList;
    int numModules;
};

typedef struct moduleInfoSet_s * moduleInfoSet;

moduleInfoSet isysNewModuleInfoSet(void);
void isysFreeModuleInfoSet(moduleInfoSet mis);
int isysReadModuleInfo(const char * filename, moduleInfoSet mis, void * path);
struct moduleInfo * isysFindModuleInfo(moduleInfoSet mis, 
				       const char * moduleName);

/* NULL moduleName indicates the end of the list; the list must be freed() */
struct moduleInfo * isysGetModuleList(moduleInfoSet mis, 
				      enum driverMajor major);

/* returns -2 for errno, -1 for unknown device */
int devMakeInode(char * devName, char * path);

int insmod(char * modName, char * path, char ** args);
int rmmod(char * modName);

/* returns 0 for true, !0 for false */
int fileIsIso(const char * file);

#endif
