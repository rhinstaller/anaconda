#include <errno.h>
#include <fcntl.h>
#include <kudzu/kudzu.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <ctype.h>

#include <linux/kd.h>

#define LOADER_OK 0
#define LOADER_BACK 1
#define LOADER_ERROR -1

char * strcasestr(char * haystack1, char * needle1) {
    char * haystack = strdup(haystack1);
    char * needle = strdup(needle1);
    char * chptr;

    for (chptr = haystack; *chptr; chptr++) *chptr = toupper(*chptr);
    for (chptr = needle; *chptr; chptr++) *chptr = toupper(*chptr);

    chptr = strstr(needle, haystack);
    if (!chptr) return NULL;

    return (chptr - haystack) + haystack1;
}

void logMessage(const char * s, ...) {
    va_list args;

    va_start(args, s);

    fprintf(stdout, "* ");
    vfprintf(stdout, s, args);
    fprintf(stdout, "\n");
    fflush(stdout);

    va_end(args);
    return;
}

char * sdupprintf(const char *format, ...) {
    char *buf = NULL;
    char c;
    va_list ap1, ap2;
    size_t size = 0;

    va_start(ap1, format);
    va_copy(ap2, ap1);
    
    /* XXX requires C99 vsnprintf behavior */
    size = vsnprintf(&c, 1, format, ap1) + 1;
    if (size == -1) {
	printf("ERROR: vsnprintf behavior is not C99\n");
	abort();
    }

    va_end(ap1);

    buf = malloc(size);
    if (buf == NULL)
	return NULL;
    vsnprintf(buf, size, format, ap2);
    va_end (ap2);

    return buf;
}

#define BEEP_TIME 150
#define BEEP_OK 1000
#define BEEP_WARN 2000
#define BEEP_ERR 4000
                                                  
static void beep(unsigned int ms, unsigned int freq)
{
    int fd, arg;
                                                                                
    fd = open("/dev/console", O_RDWR);
    if (fd < 0)
        return;
    arg = (ms << 16) | freq;
    ioctl(fd, KDMKTONE, arg);
    close(fd);
    usleep(ms*1000);
}


void mlLoadModuleSet(char * origModNames) {
    char * start, * next, * end;
    char * modNames;
    char ** initialList;
    int child, i, status;

    start = modNames = alloca(strlen(origModNames) + 1);
    strcpy(modNames, origModNames);

    next = start;
    i = 1;
    while (*next) {
        if (*next == ':') i++;
        next++;
    }
    initialList = alloca(sizeof(*initialList) * (i + 1));

    i = 0;
    while (start) {
        next = end = strchr(start, ':');
        if (next) {
            *end = '\0'; 
            next++;
        }

        initialList[i++] = start;
        start = next;
    }
    
    initialList[i] = NULL;
    for (i = 0; initialList[i]; i++) {
        if (!strlen(initialList[i]))
            continue;
        //logMessage("inserting %s", initialList[i]);
        if (!(child = fork())) {
            execl("/sbin/modprobe", "/sbin/modprobe", initialList[i], NULL);
            exit(0);
        }

        waitpid(child, &status, 0);
        logMessage("inserted %s", initialList[i]);
    }
}


char * getPcicController() {
    struct device ** devices;
    static int probed = 0;
    static char * pcic = NULL;

    if (!probed) {
        probed = 1;
 
        devices = probeDevices(CLASS_SOCKET, BUS_PCI, PROBE_ALL);
        if (devices) {
            logMessage("found cardbus pci adapter");
            pcic = "yenta_socket";
        } else {
            devices = probeDevices(CLASS_SOCKET, BUS_MISC, PROBE_ALL);
            if (devices && strcmp (devices[0]->driver, "ignore") &&
                strcmp(devices[0]->driver, "unknown") && 
                strcmp(devices[0]->driver, "disabled")) {
                logMessage("found pcmcia adapter");
                pcic = strdup(devices[0]->driver);
            }
        }

        if (!pcic) {
            logMessage("no pcic controller found");
        }
        return pcic;
    } else {
        return pcic;
    }
}

int initializePcmciaController() {
    char * pcic = NULL;
    char * mods;

    pcic = getPcicController();
    if (!pcic)
        return 0;

    mods = sdupprintf("pcmcia_core:%s:ds", pcic);
    mlLoadModuleSet(mods);

    return 0;
}



/* code from notting to activate pcmcia devices.  all kinds of wackiness */
static int pcmcia_major = 0;

static int lookup_dev(char *name) {
    FILE *f;
    int n;
    char s[32], t[32];
             
    f = fopen("/proc/devices", "r");
    if (f == NULL)
        return -errno;
    while (fgets(s, 32, f) != NULL) {
        if (sscanf(s, "%d %s", &n, t) == 2)
            if (strcmp(name, t) == 0)
                break;
    }
    fclose(f);
    if (strcmp(name, t) == 0)
        return n;
    else
        return -ENODEV;
}

static int open_sock(int sock) {
    int fd;
    char fn[64];
    dev_t dev = (pcmcia_major<<8) + sock;
        
    snprintf(fn, 64, "/tmp/pcmciadev-%d", getpid());
    if (mknod(fn, (S_IFCHR|0600), dev) == 0) {
        fd = open(fn, O_RDONLY);
        unlink(fn);
        if (fd >= 0)
            return fd;
    }
    return -1;
}

/* return whether or not we have pcmcia loaded */
int has_pcmcia(void) {
    if (pcmcia_major > 0)
        return pcmcia_major;
    pcmcia_major = lookup_dev("pcmcia");
    return pcmcia_major;
}

struct bind_info_t {
    char dev_info[32];
    unsigned char function;
    /* Not really a void *. Some convuluted structure that appears
     * to be NULL in cardmgr. */
    void *instance;
    char name[32];
    unsigned short major;
    unsigned short minor;
    void *next;
};


#define DS_BIND_REQUEST _IOWR('d', 60, struct bind_info_t)
#define DS_GET_DEVICE_INFO _IOWR('d', 61, struct bind_info_t)
int activate_pcmcia_device(struct pcmciaDevice *pdev) {
    int fd;
    struct bind_info_t * bind;
    int ret, j;

    if (has_pcmcia() <= 0) {
        logMessage("pcmcia not loaded, can't activate module");  
        return -1;
    }

    fd = open_sock(pdev->slot);
    if (fd < 0) {
        logMessage("unable to open slot");
        return -1;
    }

    bind = calloc(1, sizeof(struct bind_info_t));
    strcpy(bind->dev_info,pdev->driver);
    bind->function = pdev->function;
    logMessage("device is %s, function is %d", bind->dev_info, bind->function);
    if (ioctl(fd, DS_BIND_REQUEST, bind) != 0) {
        logMessage("failed to activate pcmcia device: %d", errno);
        beep(BEEP_TIME, BEEP_ERR);
        return LOADER_ERROR;
    }

    for (ret = j = 0; j < 10; j++) {
        logMessage("trying to get device info");
        ret = ioctl(fd, DS_GET_DEVICE_INFO, bind);
        if (ret == 0) {
            beep(BEEP_TIME, BEEP_OK);
            logMessage("succeeded");
            break;
        } else if (errno != EAGAIN) {
            beep(BEEP_TIME, BEEP_ERR);
            logMessage("failed, errno is %d", errno);
            break;
        } else {
            logMessage("EAGAIN, errno is %d", errno);
        }
        usleep(100000);
    }

    if (j >= 10)
        beep(BEEP_TIME, BEEP_ERR);

    return LOADER_OK;
}

void startPcmciaDevices() {
    struct device ** devices;
    int i;

    /* no pcmcia, don't try to start the devices */
    if (has_pcmcia() <= 0)
        return;

    devices = probeDevices(CLASS_UNSPEC, BUS_PCMCIA, 0);
    if (!devices) {
        logMessage("no devices to activate\n");
        return;
    }

    for (i = 0; devices[i]; i++) {
        if (devices[i]->bus != BUS_PCMCIA)
            continue;
        if (!(strcmp (devices[i]->driver, "ignore") && 
              strcmp (devices[i]->driver, "unknown") &&
              strcmp (devices[i]->driver, "disabled"))) 
            continue;
        
        logMessage("going to activate device using %s", devices[i]->driver);
        activate_pcmcia_device((struct pcmciaDevice *)devices[i]);
    }
}

static int detectHardware(char *** modules) {
    struct device ** devices, ** device;
    char ** modList;
    int numMods;
    char *driver;
    
    logMessage("probing buses");
    
    devices = probeDevices(CLASS_UNSPEC,
                           BUS_PCI | BUS_SBUS | 
                           ((has_pcmcia() >= 0) ? BUS_PCMCIA : 0),
                           PROBE_ALL);

    logMessage("finished bus probing");
    
    if (devices == NULL) {
        *modules = NULL;
        return LOADER_OK;
    }
    
    numMods = 0;
    for (device = devices; *device; device++) numMods++;
    
    if (!numMods) {
        *modules = NULL;
        return LOADER_OK;
    }
    
    modList = malloc(sizeof(*modList) * (numMods + 1));
    numMods = 0;
    
    for (device = devices; *device; device++) {
        driver = (*device)->driver;
        if (strcmp(driver, "usb-uhci") && strcmp(driver, "i810_audio") &&
            strcmp(driver, "orinoco_pci") && strcmp(driver, "i810_rng") &&
            strcmp(driver, "i810-tco") && strcmp(driver, "ignore") &&
            strcmp(driver, "unknown") && strcmp(driver, "disabled") &&
            strcmp(driver, "e100") && strcmp(driver, "Card") &&
            strcmp(driver, "Card:ATI Radeon Mobility 7500")) {
            modList[numMods++] = strdup(driver);
            //            logMessage("loading %s", driver);
        } else {
            //logMessage("not loading %s", driver);
        }
        
        freeDevice (*device);
    }
    
    modList[numMods] = NULL;
    *modules = modList;
    
    free(devices);
    
    return LOADER_OK;
}


int main(int argc, char ** argv) {
    char ** modList;
    char modules[1024];
    int i;

    logMessage("initializing pcmcia controller");
    initializePcmciaController();

    sleep(2);
    detectHardware(&modList);

    if (modList) {
        *modules = '\0';
        
        for (i = 0; modList[i]; i++) {
            if (i) strcat(modules, ":");
            strcat(modules, modList[i]);
        }
       
        mlLoadModuleSet(modules);
        
        sleep(2);
        startPcmciaDevices();
    }

    return 0;
}
