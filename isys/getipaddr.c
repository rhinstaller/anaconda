/*
 * getmacaddr.c - get mac address for ethernet interface
 *
 * Copyright 2003 Red Hat, Inc.
 *
 * Michael Fulbright <msf@redhat.com>
 *
 * This software may be freely redistributed under the terms of the GNU
 * general public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>


/* returns NULL or allocated string */
char *getIPAddr(char *ifname) {
  int sock;
  char *rcstr;
  struct ifreq ifr;

  if ((sock = socket(AF_INET, SOCK_DGRAM, 0)) < 0) 
      return NULL;
 
  /* Setup our control structures. */
  memset(&ifr, 0, sizeof(ifr));
  strcpy(ifr.ifr_name, ifname);

  if (ioctl(sock, SIOCGIFADDR, &ifr) < 0)
      return NULL;

  rcstr = strdup(inet_ntoa(((struct sockaddr_in *) &ifr.ifr_addr)->sin_addr));
  return rcstr;
}

#ifdef TESTING
int main() {

    printf("%s\n", getIPAddr("eth0"));
}
#endif
