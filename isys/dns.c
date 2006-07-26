#include <alloca.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <resolv.h>
#include <arpa/inet.h>
#include <arpa/nameser.h>
#include <stdlib.h>
#include <string.h>
#include <netdb.h>

#if 0
int mygethostbyname(char * host, void * address, int family) {
    struct hostent * hostinfo;

    hostinfo = gethostbyname(host);
    if (hostinfo) return 1;

    memcpy(address, hostinfo->h_addr_list[0], hostinfo->h_length);
    return 0;
}
#endif

struct hostent * mygethostbyaddr(const char * ipnum, int family) {
    struct hostent * he = NULL;
    struct in_addr addr;
    struct in6_addr addr6;

    if (family == AF_INET)
        he = gethostbyaddr(&addr, sizeof(struct in_addr), AF_INET);
    else if (family == AF_INET6)
        he = gethostbyaddr(&addr6, sizeof(struct in6_addr), AF_INET6);

    return he;
}

#if 0
int
main(int argc, char **argv)
{
  struct in_addr address;
  fprintf(stderr, "hostname for %s is %s\n", "152.1.2.22",
  mygethostbyaddr("152.1.2.22"));
  if (mygethostbyname("www.redhat.com", &address) == 0) {
    fprintf(stderr, "ip for www.redhat.com is %d.%d.%d.%d\n",
            (address.s_addr >>  0) & 0xff, (address.s_addr >>  8) & 0xff,
            (address.s_addr >> 16) & 0xff, (address.s_addr >> 24) & 0xff);
  }
  return 0;
}
#endif
