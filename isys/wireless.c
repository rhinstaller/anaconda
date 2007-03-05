/*
 * wireless.c - wireless card manipulation
 *
 * Copyright 2004  Red Hat, Inc.
 * 
 * Some portions from wireless_tools 
 *    copyright (c) 1997-2003 Jean Tourrilhes <jt@hpl.hp.com>
 *
 * Jeremy Katz <katzj@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <sys/socket.h>
#include <sys/types.h>

#include <linux/types.h>
#include <linux/if.h>
#include <linux/wireless.h>

static struct iwreq get_wreq(char * ifname) {
    struct iwreq wreq;

    memset(&wreq, 0, sizeof(wreq));
    strncpy(wreq.ifr_name, ifname, IFNAMSIZ);
    
    return wreq;
}

static int get_socket() {
    int sock;

    if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
#ifdef STANDALONE
        fprintf(stderr, "Error creating socket: %s\n", strerror(errno));
#endif
        return -1;
    }

    return sock;
}

int is_wireless_interface(char * ifname) {
    int sock = get_socket();
    struct iwreq wreq = get_wreq(ifname);

    int rc = ioctl(sock, SIOCGIWNAME, &wreq);
    close(sock);

    if (rc < 0) {
        return 0;
    }

    return 1;
}

/* set the essid for ifname to essid.  if essid is NULL, do automatically */
int set_essid(char * ifname, char * essid) {
    int sock; 
    struct iwreq wreq;

    memset(&wreq, 0, sizeof (wreq));

    if (strlen(essid) > IW_ESSID_MAX_SIZE) {
        fprintf(stderr, "essid too long\n");
        return -1;
    }

    sock = get_socket();
    wreq = get_wreq(ifname);

    if (essid) {
        wreq.u.essid.flags = 1;
        wreq.u.essid.pointer = (caddr_t) essid;
        wreq.u.essid.length = strlen(essid) + 1;
    } else {
        wreq.u.essid.flags = 0;
        wreq.u.essid.pointer = (caddr_t) NULL;
        wreq.u.essid.length = 0;
    }

    int rc = ioctl(sock, SIOCSIWESSID, &wreq);
    close(sock);

    if (rc < 0) {
        fprintf(stderr, "failed to set essid: %s\n", strerror(errno));
        return -1;
    }

    return 0;
}

char * get_essid(char * ifname) {
    int sock; 
    struct iwreq wreq; 

    memset(&wreq, 0, sizeof (wreq));

    sock = get_socket();
    wreq = get_wreq(ifname);

    wreq.u.essid.pointer = (caddr_t) malloc(IW_ESSID_MAX_SIZE + 1);
    wreq.u.essid.length = IW_ESSID_MAX_SIZE + 1;
    wreq.u.essid.flags = 0;
    int rc = ioctl(sock, SIOCGIWESSID, &wreq);
    close(sock);

    if (rc < 0) {
        fprintf(stderr, "failed to get essid for %s: %s\n", ifname, 
                strerror(errno));
        return NULL;
    }

    return wreq.u.essid.pointer;
}

/* based off iw_in_key from wireless-tools/iwlib.c */
static int parse_wep_key(char * in, unsigned char * key) {
    int len = 0;

    if (!strncmp(in, "s:", 2)) {
        /* the key is a string */
        len = strlen(in + 2);
	memmove(key, in + 2, len);
    } else {
        char *buff, *hex, *out, *p;

        /* hexadecimal digits, straight from iwlib.c */
        buff = malloc(IW_ENCODING_TOKEN_MAX + strlen(in) + 1);
        if(buff == NULL) {
            fprintf(stderr, "Malloc failed (string too long ?)\n");
            return(-1);
        }
        /* Preserve original buffers (both in & out) */
        hex = buff + IW_ENCODING_TOKEN_MAX;
        strcpy(hex, in);
        out = buff;
        /* Parse */
        p = strtok(hex, "-:;.,");
        while((p != (char *) NULL) && (len < IW_ENCODING_TOKEN_MAX)) {
            int temph, templ, count, l;

            /* Get each char separatly (and not by two) so that we don't
             * get confused by 'enc' (=> '0E'+'0C') and similar */
            count = sscanf(p, "%1X%1X", &temph, &templ);
            if(count < 1)
              return(-1);               /* Error -> non-hex char */
            /* Fixup odd strings such as '123' is '01'+'23' and not '12'+'03'*/
            l = strlen(p);
            if(l % 2)
              count = 1;
            /* Put back two chars as one byte */
            if(count == 2)
              templ |= temph << 4;
            else
              templ = temph;
            out[len++] = (unsigned char) (templ & 0xFF);
            /* Check where to get next char from */
            if(l > count)     /* Token not finished yet */
              p += count;
            else
              p = strtok((char *) NULL, "-:;.,");
          }
        memcpy(key, out, len);
        free(buff);
    }

    return len;
}

int set_wep_key(char * ifname, char * key) {
    int sock; 
    struct iwreq wreq; 
    unsigned char thekey[IW_ENCODING_TOKEN_MAX];
    
    if (strlen(key) > IW_ENCODING_TOKEN_MAX) {
        fprintf(stderr, "wep key too long\n");
        return -1;
    }

    sock = get_socket();
    wreq = get_wreq(ifname);

    if (key) {
        int len = parse_wep_key(key, thekey);
        if (len > 0) {
            wreq.u.data.flags = IW_ENCODE_ENABLED;
            wreq.u.data.length = len;
            wreq.u.data.pointer = (caddr_t) thekey;
        }
    } else {
        wreq.u.data.flags = IW_ENCODE_DISABLED;
        wreq.u.data.pointer = (caddr_t) NULL;
        wreq.u.data.length = 0;
    }

    int rc = ioctl(sock, SIOCSIWENCODE, &wreq);
    close(sock);

    if (rc < 0) {
        fprintf(stderr, "failed to set wep key: %s\n", strerror(errno));
        return -1;
    }

    return 0;
}

enum { MODE_AUTO, MODE_ADHOC, MODE_MANAGED, MODE_MASTER, MODE_REPEATER,
       MODE_SECONDARY, MODE_MONITOR };

int set_managed(char * ifname) {
    int sock = get_socket();
    struct iwreq wreq = get_wreq(ifname);

    wreq.u.mode = MODE_MANAGED;
    int rc = ioctl(sock, SIOCSIWMODE, &wreq);
    close(sock);

    if (rc < 0) {
        fprintf(stderr, "failed to set managed mode: %s\n", strerror(errno));
        return -1;
    }

    return 0;
}

#ifdef STANDALONE
int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s [interface] [essid] [key]\n", argv[0]);
        exit(1);
    }

    if (!is_wireless_interface(argv[1])) {
        fprintf(stderr, "%s isn't a wireless interface!\n", argv[1]);
        exit(2);
    } 

    /*    if (set_essid(argv[1], NULL) < 0) {
        fprintf(stderr, "Unable to set essid to %s\n", argv[2]);
        exit(3);
    }
    exit(0);*/

    if (set_essid(argv[1], argv[2]) < 0) {
        fprintf(stderr, "Unable to set essid to %s\n", argv[2]);
        exit(3);
    }

    /*    if (set_wep_key(argv[1], NULL) < 0) {
        fprintf(stderr, "Unable to set wepkey to %s\n", argv[2]);
        exit(4);
    }
    exit(0);*/

    if (set_wep_key(argv[1], argv[3]) < 0) {
        fprintf(stderr, "Unable to set wepkey to %s\n", argv[2]);
        exit(4);
    }

    return 0;
}
#endif
