#ifndef WIRELESS_H
#define WIRELESS_H

int is_wireless_interface(char * ifname);
int set_essid(char * ifname, char * essid);
char * get_essid(char * ifname);
int set_wep_key(char * ifname, char * key);
int set_managed(char * ifname);

#endif
