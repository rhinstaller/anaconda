#ifndef H_PROBE
#define H_PROBE

#include "kudzu/kudzu.h"

#define DASD_IOCTL_LETTER 'D'
#define BIODASDINFO    _IOR(DASD_IOCTL_LETTER,1,dasd_information_t)

struct kddevice {
    char * name;		/* malloced */
    char * model;
    enum deviceClass class;
    int code;
};

struct knownDevices {
    struct kddevice * known;
    int numKnown;
    int numKnownAlloced;
};

#if defined(__s390__) || defined(__s390x__)
/*
 * struct dasd_information_t
 * represents any data about the data, which is visible to userspace
 */
typedef struct dasd_information_t {
        unsigned int devno; /* S/390 devno */
        unsigned int real_devno; /* for aliases */
        unsigned int schid; /* S/390 subchannel identifier */
        unsigned int cu_type  : 16; /* from SenseID */
        unsigned int cu_model :  8; /* from SenseID */
        unsigned int dev_type : 16; /* from SenseID */
        unsigned int dev_model : 8; /* from SenseID */
        unsigned int open_count;
        unsigned int req_queue_len;
        unsigned int chanq_len;
        char type[4]; /* from discipline.name, 'none' for unknown */
        unsigned int status; /* current device level */
        unsigned int label_block; /* where to find the VOLSER */
        unsigned int FBA_layout; /* fixed block size (like AIXVOL) */
        unsigned int characteristics_size;
        unsigned int confdata_size;
        char characteristics[64]; /* from read_device_characteristics */
        char configuration_data[256]; /* from read_configuration_data */
} dasd_information_t;

typedef struct cchhb
{
        u_int16_t cc;
        u_int16_t hh;
        u_int8_t b;
} __attribute__ ((packed)) cchhb_t;

typedef struct volume_label
{
        char volkey[4];         /* volume key = volume label                 */
        char vollbl[4];         /* volume label                              */
        char volid[6];          /* volume identifier                         */
        u_int8_t security;              /* security byte                             */
        cchhb_t vtoc;           /* VTOC address                              */
        char res1[5];           /* reserved                                  */
        char cisize[4];         /* CI-size for FBA,...                       */
                                /* ...blanks for CKD                         */
        char blkperci[4];       /* no of blocks per CI (FBA), blanks for CKD */
        char labperci[4];       /* no of labels per CI (FBA), blanks for CKD */
        char res2[4];           /* reserved                                  */
        char lvtoc[14];         /* owner code for LVTOC                      */
        char res3[29];          /* reserved                                  */
} __attribute__ ((packed)) volume_label_t;
#endif


/* 0 if the device should be filtered from the list, 1 if it should be 
   included */
typedef int (*kdFilterType)(const struct kddevice * dev);

struct knownDevices kdInit(void);
int kdFindNetList(struct knownDevices * devices, int code);
int kdFindDasdList(struct knownDevices * devices, int code);
int kdFindIdeList(struct knownDevices * devices, int code);
int kdFindFilteredIdeList(struct knownDevices * devices, int code, 
			  kdFilterType filter);
int kdFindScsiList(struct knownDevices * devices, int code);
void kdFree(struct knownDevices * devices);
void kdAddDevice(struct knownDevices * devices, enum deviceClass devClass, 
		 char * devName, char * devModel);
char *getDasdPorts();
int isLdlDasd(char * dev);

int vioGetDasdDevs(struct knownDevices * devices);
int vioGetCdDevs(struct knownDevices * devices);

int readFD (int fd, char **buf);
void addDevice(struct knownDevices * devices, struct kddevice dev);
int deviceKnown(struct knownDevices * devices, char * dev);
int isUsableDasd(char *device);
#endif
