#include <alloca.h>
#include <sys/socket.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <resolv.h>
#include <arpa/nameser.h>
#include <stdlib.h>
#include <string.h>

/* This is dumb, but glibc doesn't like to do hostname lookups w/o libc.so */

union dns_response{
    HEADER hdr;
    u_char buf[PACKETSZ];
} ;

static int doQuery(char * query, int queryType,
		   char ** domainName, struct in_addr * ipNum) {
    int len, ancount, type;
    u_char * data, * end;
    char name[MAXDNAME];
    union dns_response response;

    /* Give time to finish ethernet negotiation */
    _res.retry = 3;

    len = res_search(query, C_IN, queryType, (void *) &response, 
		    sizeof(response));
    if (len <= 0) return -1;

    if (ntohs(response.hdr.rcode) != NOERROR) return -1;
    ancount = ntohs(response.hdr.ancount);
    if (ancount < 1) return -1;

    data = response.buf + sizeof(HEADER);
    end = response.buf + len;
    
    /* skip the question */
    data += dn_skipname(data, end) + QFIXEDSZ;

    /* parse the answer(s) */
    while (--ancount >= 0 && data < end) {

      /* skip the domain name portion of the RR record */
      data += dn_skipname(data, end);

      /* get RR information */
      GETSHORT(type, data);
      data += INT16SZ; /* skipp class */
      data += INT32SZ; /* skipp TTL */
      GETSHORT(len,  data);

      if (type == T_PTR) {
	/* we got a pointer */
	len = dn_expand(response.buf, end, data, name, sizeof(name));
	if (len <= 0) return -1;
	if (queryType == T_PTR && domainName) {
	  /* we wanted a pointer */
	  *domainName = malloc(strlen(name) + 1);
	  strcpy(*domainName, name);
	  return 0;
	}
      } else if (type == T_A) {
	/* we got an address */
	if (queryType == T_A && ipNum) {
	  /* we wanted an address */
	  memcpy(ipNum, data, sizeof(*ipNum));
	  return 0;
	}
      }

      /* move ahead to next RR */
      data += len;
    } 

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
