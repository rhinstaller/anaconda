#include <alloca.h>
#include <sys/socket.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <resolv.h>
#include <arpa/inet.h>
#include <arpa/nameser.h>
#include <stdlib.h>
#include <string.h>

/* This is dumb, but glibc doesn't like to do hostname lookups w/o libc.so */

#ifndef DIET
union dns_response{
    HEADER hdr;
    u_char buf[PACKETSZ];
} ;

static int doQuery(char * query, int queryType,
		   char ** domainName, struct in_addr * ipNum) {
    int len, ancount, type;
    u_char * data, * end;
    char name[MAXDNAME];
    union dns_response static_response, *response = &static_response;
    size_t response_len = sizeof(static_response);

    /* Give time to finish ethernet negotiation */
    _res.retry = 3;

    do {
      len = res_search(query, C_IN, queryType, (void*) response, 
                       response_len);
      if (len <= 0) return -1;
      if (len < response_len) break;
      if (response != &static_response) free(response);
      if (len > 0x10000) return -1;
      response_len = len + 1024;
      response = malloc(response_len);
      if (response == NULL) return -1;
    } while (1);

    if (len < sizeof(response->hdr)) {
      if (response != &static_response) free(response);
      return -1;
    }
    if (ntohs(response->hdr.rcode) != NOERROR) {
      if (response != &static_response) free(response);
      return -1;
    }
    ancount = ntohs(response->hdr.ancount);
    if (ancount < 1) {
      if (response != &static_response) free(response);
      return -1;
    }

    data = response->buf + sizeof(HEADER);
    end = response->buf + len;
    
    /* skip the question */
    len = dn_skipname(data, end);
    if (len <= 0) {
      if (response != &static_response) free(response);
      return -1;
    }
    data += len + QFIXEDSZ;

    /* parse the answer(s) */
    while (--ancount >= 0 && data < end) {

      /* skip the domain name portion of the RR record */
      data += dn_skipname(data, end);

      /* get RR information */
      if (data + 3 * INT16SZ + INT32SZ > end) {
          if (response != &static_response) free(response);
          return -1;
      }
      GETSHORT(type, data);
      data += INT16SZ; /* skip class */
      data += INT32SZ; /* skip TTL */
      GETSHORT(len,  data);

      if (type == T_PTR) {
	/* we got a pointer */
	len = dn_expand(response->buf, end, data, name, sizeof(name));
	if (len <= 0) {
          if (response != &static_response) free(response);
          return -1;
        }
	if (queryType == T_PTR && domainName) {
	  /* we wanted a pointer */
	  *domainName = malloc(strlen(name) + 1);
	  strcpy(*domainName, name);
          if (response != &static_response) free(response);
	  return 0;
	}
      } else if (type == T_A) {
	/* we got an address */
	if (queryType == T_A && ipNum) {
	  /* we wanted an address */
	  memcpy(ipNum, data, sizeof(*ipNum));
          if (response != &static_response) free(response);
	  return 0;
	}
      }

      /* move ahead to next RR */
      data += len;
    } 

    if (response != &static_response) free(response);
    return -1;
}

char * mygethostbyaddr(char * ipnum) {
    int rc;
    char * result;
    char * strbuf;
    char * chptr;
    char * splits[4];
    int i;

    _res.retry = 1;

    strbuf = alloca(strlen(ipnum) + 1);
    strcpy(strbuf, ipnum);

    ipnum = alloca(strlen(strbuf) + 20);

    for (i = 0; i < 4; i++) {
	chptr = strbuf;
	while (*chptr && *chptr != '.') chptr++;
	*chptr = '\0';

	if (chptr - strbuf > 3) return NULL;
	splits[i] = strbuf;
	strbuf = chptr + 1;
    }

    sprintf(ipnum, "%s.%s.%s.%s.in-addr.arpa", splits[3], splits[2],
	    splits[1], splits[0]);

    rc = doQuery(ipnum, T_PTR, &result, NULL);
    if (rc)
	rc = doQuery(ipnum, T_PTR, &result, NULL);

    if (rc) 
	return NULL;
    else
	return result;
}

int mygethostbyname(char * name, struct in_addr * addr) {
    return doQuery(name, T_A, NULL, addr);
}

#else
#include <netdb.h>
#include <sys/socket.h>
#include <string.h>

int mygethostbyname(char * host, struct in_addr * address) {
    struct hostent * hostinfo;

    hostinfo = gethostbyname(host);
    if (!hostinfo) return 1;

    memcpy(address, hostinfo->h_addr_list[0], hostinfo->h_length);
    return 0;
}

char * mygethostbyaddr(const char * ipnum) {
    struct hostent * he;
    struct in_addr addr;

    if (!inet_aton(ipnum, &addr)) 
	return NULL;
    
    he = gethostbyaddr(&addr, sizeof(struct in_addr), AF_INET);
    if (he)
        return he->h_name;
    else
        return NULL;
}

#endif

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
