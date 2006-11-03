#include <alloca.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <resolv.h>
#include <arpa/inet.h>
#include <arpa/nameser.h>
#include <stdlib.h>
#include <string.h>

#include "dns.h"

/* This is dumb, but glibc doesn't like to do hostname lookups w/o libc.so */

/*
 * IPv6 DNS extensions documented here:
 * http://tools.ietf.org/html/rfc3596
 */

union dns_response{
    HEADER hdr;
    u_char buf[PACKETSZ];
};

static int doQuery(char * query, int queryType,
                   char ** domainName, void * ipNum, int family) {
    int len, ancount, type;
    u_char * data, * end;
    char name[MAXDNAME];
    union dns_response static_response, *response = &static_response;
    size_t response_len = sizeof(static_response);

    /* Give time to finish ethernet negotiation */
    _res.retry = 3;

    do {
        len = res_search(query, C_IN, queryType, (void*)response, response_len);
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
            /* we have an IPv4 address */
            if (queryType == T_A && ipNum) {
                memcpy(ipNum, data, sizeof(struct in_addr));
                if (response != &static_response)
					free(response);
                return 0;
            }
        } else if (type == T_AAAA) {
			/* we have an IPv6 address */
            if (queryType == T_AAAA && ipNum) {
                memcpy(ipNum, data, sizeof(struct in6_addr));
                if (response != &static_response)
                    free(response);
                return 0;
            }
		}

        /* move ahead to next RR */
        data += len;
    }

    if (response != &static_response) free(response);
    return -1;
}

char * mygethostbyaddr(char * ipnum, int family) {
    int i, j, ret;
    char *buf = NULL;
    char sbuf[5];
    char *result = NULL;
    char *octets[4];
    char *octet = NULL;
    char *parts[8];
    char *partptr = NULL;
    struct in6_addr addr6;

    _res.retry = 1;

    if (ipnum == NULL || (family != AF_INET && family != AF_INET6))
        return NULL;

    if (family == AF_INET) {
        buf = strdup(ipnum);
        octet = strtok(buf, ".");

        i = 0;
        while (octet != NULL) {
            octets[i] = octet;
            i++;
            octet = strtok(NULL, ".");
        }

        if (i == 4) {
            if (asprintf(&ipnum, "%s.%s.%s.%s.in-addr.arpa", octets[3],
                         octets[2], octets[1], octets[0]) == -1)
                return NULL;
        } else {
            return NULL;
        }

        free(buf);
        buf = NULL;
    } else if (family == AF_INET6) {
        if (!inet_pton(AF_INET6, ipnum, &addr6))
            return NULL;

        i = 7;
        while (i >= 0) {
            sprintf(sbuf, "%4x", ntohs(addr6.s6_addr16[i]));
            sbuf[4] = '\0';

            if ((parts[i] = malloc(8)) == NULL)
                return NULL;

            partptr = parts[i];

            for (j = 3; j >= 0; j--) {
                if (sbuf[j] == ' ')
                    *partptr = '0';
                else
                    *partptr = sbuf[j];

                partptr++;

                if (j != 0) {
                    *partptr = '.';
                    partptr++;
                }
            }

            i--;
        }

        if (asprintf(&ipnum, "%s.%s.%s.%s.%s.%s.%s.%s.ip6.arpa", parts[7],
                     parts[6], parts[5], parts[4], parts[3], parts[2],
                     parts[1], parts[0]) == -1)
            return NULL;

        for (j = 0; j < 8; j++) {
            free(parts[j]);
            parts[j] = NULL;
        }
    }

    ret = doQuery(ipnum, T_PTR, &result, NULL, family);
    if (ret)
        ret = doQuery(ipnum, T_PTR, &result, NULL, family);

    if (ret) 
        return NULL;
    else
        return result;
}

int mygethostbyname(char * name, void * addr, int family) {
    int type;

    if (family == AF_INET)
        type = T_A;
    else if (family == AF_INET6)
        type = T_AAAA;
    else
        type = -1;

    return doQuery(name, type, NULL, addr, family);
}

#if 0
int main(int argc, char **argv) {
    struct in_addr addr;
    struct in6_addr addr6;
    char *ret = NULL;

    /* IPv4 tests */
    printf("hostname for %s is %s\n", "152.1.2.22",
           mygethostbyaddr("152.1.2.22", AF_INET));
    if (mygethostbyname("www.redhat.com", &addr, AF_INET) == 0) {
        ret = malloc(48);
        inet_ntop(AF_INET, &addr, ret, INET_ADDRSTRLEN);
        printf("ip for www.redhat.com is %s\n", ret);
        free(ret);
        ret = NULL;
    }

    /* IPv6 tests */
    printf("hostname for %s is %s\n", "fec0:acdc:1::1",
           mygethostbyaddr("fec0:acdc:1::1", AF_INET6));
    if (mygethostbyname("cutlet.ipv6.install.boston.redhat.com", &addr6, AF_INET6) == 0) {
        ret = malloc(48);
        inet_ntop(AF_INET6, &addr6, ret, INET6_ADDRSTRLEN);
        printf("ip for cutlet.ipv6.install.boston.redhat.com is %s\n", ret);
        free(ret);
        ret = NULL;
    }

    return 0;
}
#endif

/* vim:set shiftwidth=4 softtabstop=4: */
