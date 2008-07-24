#ifndef ISYSNET_H
#define ISYSNET_H

#include <linux/types.h>
#include <linux/ethtool.h>

/* type definitions so that the kernel-ish includes can be shared */
#ifndef uint8_t
#  define uint8_t       unsigned char
#endif
#ifndef uint16_t
#  define uint16_t      unsigned short int
#endif
#ifndef uint32_t
#  define uint32_t      unsigned int
#endif
#ifndef uint64_t
#  define uint64_t      unsigned long long int
#endif
typedef uint64_t u64;
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;

/* returns 1 for link, 0 for no link, -1 for unknown */
int get_link_status(char *ifname);

typedef enum ethtool_speed_t { ETHTOOL_SPEED_UNSPEC = -1, 
                               ETHTOOL_SPEED_10 = SPEED_10, 
                               ETHTOOL_SPEED_100 = SPEED_100,
                               ETHTOOL_SPEED_1000 = SPEED_1000 } ethtool_speed;
typedef enum ethtool_duplex_t { ETHTOOL_DUPLEX_UNSPEC = -1, 
                                ETHTOOL_DUPLEX_HALF = DUPLEX_HALF,
                                ETHTOOL_DUPLEX_FULL = DUPLEX_FULL } ethtool_duplex;

/* set ethtool settings */
int setEthtoolSettings(char * dev, ethtool_speed speed, ethtool_duplex duplex);
int identifyNIC(char *iface, int seconds);

#endif
