/* silo.c: Conversions between SCSI and IDE disk names
 *	   and OpenPROM fully qualified paths.
 *
 * Copyright (C) 1999, 2000 Jakub Jelinek <jakub@redhat.com>
 * 
 * This software may be freely redistributed under the terms of the GNU
 * public license.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <asm/openpromio.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/utsname.h>

#ifndef OPROMSETCUR
#define OPROMSETCUR	0x20004FF0
#define OPROMPCI2NODE	0x20004FF1
#define OPROMPATH2NODE	0x20004FF2
#endif

static int hasaliases;
static char *promdev = "/dev/openprom";
static int promfd;
static char sd_targets[10] = "31204567";
static int p1275 = 0;
static int prom_root_node, prom_current_node;
static int promvers;
static void (*prom_walk_callback)(int node);
static char prom_path[1024];
#define MAX_PROP	128
#define MAX_VAL		(4096-128-4)
static char buf[4096];
static char regstr[40];
#define DECL_OP(size) struct openpromio *op = (struct openpromio *)buf; op->oprom_size = (size)

static int
prom_setcur(int node) {
    DECL_OP(sizeof(int));
    
    if (node == -1) return 0;
    *(int *)op->oprom_array = node;
    if (ioctl (promfd, OPROMSETCUR, op) < 0)
        return 0;
    prom_current_node = *(int *)op->oprom_array;
    return *(int *)op->oprom_array;
}

static int
prom_getsibling(int node) {
    DECL_OP(sizeof(int));
    
    if (node == -1) return 0;
    *(int *)op->oprom_array = node;
    if (ioctl (promfd, OPROMNEXT, op) < 0)
        return 0;
    prom_current_node = *(int *)op->oprom_array;
    return *(int *)op->oprom_array;
}

static int
prom_getchild(int node) {
    DECL_OP(sizeof(int));
    
    if (!node || node == -1) return 0;
    *(int *)op->oprom_array = node;
    if (ioctl (promfd, OPROMCHILD, op) < 0)
        return 0;
    prom_current_node = *(int *)op->oprom_array;
    return *(int *)op->oprom_array;
}

static char *
prom_getproperty(char *prop, int *lenp) {
    DECL_OP(MAX_VAL);
    
    strcpy (op->oprom_array, prop);
    if (ioctl (promfd, OPROMGETPROP, op) < 0)
        return 0;
    if (lenp) *lenp = op->oprom_size;
    return op->oprom_array;
}

static char *
prom_getopt(char *var, int *lenp) {
    DECL_OP(MAX_VAL);

    strcpy (op->oprom_array, var);
    if (ioctl (promfd, OPROMGETOPT, op) < 0)
        return 0;
    if (lenp) *lenp = op->oprom_size;
    return op->oprom_array;
}

static void
prom_setopt(char *var, char *value) {
    DECL_OP(MAX_VAL);

    strcpy (op->oprom_array, var);
    strcpy (op->oprom_array + strlen (var) + 1, value);
    ioctl (promfd, OPROMSETOPT, op);
}

static int
prom_getbool(char *prop) {
    DECL_OP(0);

    *(int *)op->oprom_array = 0;
    for (;;) {
        op->oprom_size = MAX_PROP;
            if (ioctl(promfd, OPROMNXTPROP, op) < 0)
                return 0;
            if (!op->oprom_size)
                return 0;
            if (!strcmp (op->oprom_array, prop))
                return 1;
    }
}

static int
prom_pci2node(int bus, int devfn) {
    DECL_OP(2*sizeof(int));
    
    ((int *)op->oprom_array)[0] = bus;
    ((int *)op->oprom_array)[1] = devfn;
    if (ioctl (promfd, OPROMPCI2NODE, op) < 0)
        return 0;
    prom_current_node = *(int *)op->oprom_array;
    return *(int *)op->oprom_array;
}

static int
prom_path2node(char *path) {
    DECL_OP(MAX_VAL);
    
    strcpy (op->oprom_array, path);
    if (ioctl (promfd, OPROMPATH2NODE, op) < 0)
        return 0;
    prom_current_node = *(int *)op->oprom_array;
    return *(int *)op->oprom_array;
}

#define PW_TYPE_SBUS	1
#define PW_TYPE_PCI	2
#define PW_TYPE_EBUS	3

static void
prom_walk(char *path, int parent, int node, int type) {
    int nextnode;
    int len, ntype = type;
    char *prop;
    
    prop = prom_getproperty("name", &len);
    if (prop && len > 0) {
        if ((!strcmp(prop, "sbus") || !strcmp(prop, "sbi")) && !type)
            ntype = PW_TYPE_SBUS;
        else if (!strcmp(prop, "ebus") && type == PW_TYPE_PCI)
            ntype = PW_TYPE_EBUS;
        else if (!strcmp(prop, "pci") && !type)
            ntype = PW_TYPE_PCI;
    }
    *path = '/';
    strcpy (path + 1, prop);
    prop = prom_getproperty("reg", &len);
    if (prop && len >= 4) {
        unsigned int *reg = (unsigned int *)prop;
        int cnt = 0;
        if (!p1275 || (type == PW_TYPE_SBUS))
	    sprintf (regstr, "@%x,%x", reg[0], reg[1]);
        else if (type == PW_TYPE_PCI) {
	    if ((reg[0] >> 8) & 7)
		sprintf (regstr, "@%x,%x", (reg[0] >> 11) & 0x1f, (reg[0] >> 8) & 7);
	    else
		sprintf (regstr, "@%x", (reg[0] >> 11) & 0x1f);
        } else if (len == 4)
	    sprintf (regstr, "@%x", reg[0]);
        else {
	    unsigned int regs[2];

	    /* Things get more complicated on UPA. If upa-portid exists,
	       then address is @upa-portid,second-int-in-reg, otherwise
	       it is @first-int-in-reg/16,second-int-in-reg (well, probably
	       upa-portid always exists, but just to be safe). */
	    memcpy (regs, reg, sizeof(regs));
	    prop = prom_getproperty("upa-portid", &len);
	    if (prop && len == 4) {
		reg = (unsigned int *)prop;
		sprintf (regstr, "@%x,%x", reg[0], regs[1]); 
	    } else
	        sprintf (regstr, "@%x,%x", regs[0] >> 4, regs[1]);
	}
        for (nextnode = prom_getchild(parent); nextnode; nextnode = prom_getsibling(nextnode)) {
	    prop = prom_getproperty("name", &len);
	    if (prop && len > 0 && !strcmp (path + 1, prop))
		cnt++;
	}
        if (cnt > 1)
	    strcat (path, regstr);
    }

    prom_walk_callback(node);

    nextnode = prom_getchild(node);
    if (nextnode)
        prom_walk(strchr (path, 0), node, nextnode, ntype);
    nextnode = prom_getsibling(node);
    if (nextnode)
        prom_walk(path, parent, nextnode, type);
}

static int
prom_init(int mode) {    
    struct utsname u;

    promfd = open(promdev, mode);
    if (promfd == -1)
	return -1;
    prom_root_node = prom_getsibling(0);
    if (!prom_root_node)
	return -1;

    if (!uname (&u) && !strcmp (u.machine, "sparc64"))
	p1275 = 1;
    return 0;
}

#define SDSK_TYPE_IDE	1
#define SDSK_TYPE_SD	2
#define SDSK_TYPE_PLN	3
#define SDSK_TYPE_FC	4

static struct sdsk_disk {
    unsigned int prom_node;
    unsigned int type, host, hi, mid, lo;
    unsigned char *prom_name;
} *hd = NULL, *sd = NULL;
static int hdlen, sdlen;

static void
scan_walk_callback(int node) {
    int nextnode;
    char *prop;
    int len, disk;
    static int v0ctrl = 0;

    for (disk = 0; disk < hdlen + sdlen; disk++) {
	if (hd[disk].prom_node == node) {
	    switch (hd[disk].type) {
	    case SDSK_TYPE_IDE:
		for (nextnode = prom_getchild(node); nextnode; nextnode = prom_getsibling(nextnode)) {
		    prop = prom_getproperty("name", &len);
		    if (prop && len > 0 && (!strcmp (prop, "ata") || !strcmp (prop, "disk")))
			break;
		}
		if (!nextnode)
		    continue;
		if (prop[0] == 'a')
		    sprintf (prop, "/ata@%x,0/cmdk@%x,0", hd[disk].hi, hd[disk].lo);
		else
		    sprintf (prop, "/disk@%x,0", hd[disk].hi * 2 + hd[disk].lo);
		break;
	    case SDSK_TYPE_SD:
		for (nextnode = prom_getchild(node); nextnode; nextnode = prom_getsibling(nextnode)) {
		    prop = prom_getproperty("compatible", &len);
		    if (prop && len > 0 && !strcmp (prop, "sd"))
			break;
		    prop = prom_getproperty("name", &len);
		    if (prop && len > 0 && (!strcmp (prop, "sd") || !strcmp (prop, "disk")))
			break;
		}
		if (!nextnode || hd[disk].hi)
		    continue;
		if (promvers) {
		    char name[1024];
		    prop = prom_getproperty("name", &len);
		    if (prop && len > 0)
			strcpy (name, prop);
		    else
			strcpy (name, "sd");
		    if (!prop)
			prop = ((struct openpromio *)buf)->oprom_array;
		    sprintf (prop, "/%s@%x,%x", name, hd[disk].mid, hd[disk].lo);
		} else {
		    int i;
		    for (i = 0; sd_targets[i]; i++)
			if (sd_targets[i] == '0' + hd[disk].mid)
			    break;
		    if (!sd_targets[i])
			i = hd[disk].mid;
		    sprintf (prop, "sd(%d,%d,", v0ctrl, i);
		}
		break;
	    case SDSK_TYPE_PLN:
		prop = ((struct openpromio *)buf)->oprom_array;
		sprintf (prop, "/SUNW,pln@%x,%x/SUNW,ssd@%x,%x",
			 hd[disk].lo & 0xf0000000, hd[disk].lo & 0xffffff,
			 hd[disk].hi, hd[disk].mid);
		break;
	    case SDSK_TYPE_FC:
		prop = ((struct openpromio *)buf)->oprom_array;
		sprintf (prop, "/sf@0,0/ssd@w%08x%08x,%x", hd[disk].hi, hd[disk].mid, hd[disk].lo);
		break;
	    default:
		continue;
	    }
	    hd[disk].prom_name = malloc (strlen (prom_path) + strlen(prop) + 3);
	    if (!hd[disk].prom_name)
		continue;
	    if (promvers)
		strcpy (hd[disk].prom_name, prom_path);
	    else
		hd[disk].prom_name[0] = '\0';
	    strcat (hd[disk].prom_name, prop);
	}
    }
    v0ctrl++;
}

static int
scan_ide(void) {
    DIR * dir;
    char path[80];
    char buffer[512];
    int fd, i, disk;
    struct dirent * ent;
    int pci_bus, pci_devfn;

    if (access("/proc/ide", R_OK)) return 0;

    if (!(dir = opendir("/proc/ide"))) {
	return 1;
    }

    while ((ent = readdir(dir))) {
	if (ent->d_name[0] == 'h' && ent->d_name[1] == 'd' &&
	    ent->d_name[2] >= 'a' && ent->d_name[2] <= 'z' &&
	    ent->d_name[3] == '\0') {
	    disk = ent->d_name[2] - 'a';
	    if (disk >= hdlen) {
		hd = (struct sdsk_disk *)realloc(hd, ((disk&~3)+4)*sizeof(struct sdsk_disk));
		memset (hd + hdlen, 0, ((disk&~3)+4-hdlen)*sizeof(struct sdsk_disk));
		hdlen = (disk&~3)+4;
	    }
	    for (i = (disk & ~3); i <= (disk | 3); i++) {
		if (hd[i].type)
		    break;
	    }
	    if (i > (disk | 3)) {
		sprintf(path, "/proc/ide/%s", ent->d_name);
		if (readlink(path, buffer, 512) < 5)
		    continue;
		if (strncmp(buffer, "ide", 3) ||
		    !isdigit(buffer[3]) ||
		    buffer[4] != '/')
		    continue;
		buffer[4] = 0;
		sprintf(path, "/proc/ide/%s/config", buffer);
		if ((fd = open(path, O_RDONLY)) < 0)
		    continue;
		i = read(fd, buffer, 50);
		close(fd);
		if (i < 50) continue;
		if (sscanf (buffer, "pci bus %x device %x ",
			    &pci_bus, &pci_devfn) != 2)
			continue;
		hd[disk].prom_node = prom_pci2node (pci_bus, pci_devfn);
	    } else
	    	hd[disk].prom_node = hd[i].prom_node;
	    hd[disk].type = SDSK_TYPE_IDE;
	    hd[disk].hi = (disk & 2) >> 1;
	    hd[disk].lo = (disk & 1);
	}
    }

    closedir(dir);

    return 0;
}

static int
scan_scsi(void) {
    FILE *f;
    DIR * dir, *dirhba;
    struct dirent * ent, *enthba;
    struct stat st;
    char * p, * q;
    char buf[512];
    char path[128];
    int disk = 0;
    int host, channel, id, lun;
    int prom_node, pci_bus, pci_devfn;

    if (access("/proc/scsi/scsi", R_OK)) {
	return 0;
    }

    f = fopen("/proc/scsi/scsi", "r");
    if (f == NULL) return 1;

    if (fgets(buf, sizeof(buf), f) == NULL) {
	fclose(f);
	return 1;
    }
    if (!strcmp(buf, "Attached devices: none\n")) {
	fclose(f);
	return 0;
    }

    while (fgets(buf, sizeof(buf), f) != NULL) {
	if (sscanf(buf, "Host: scsi%d Channel: %d Id: %d Lun: %d\n",
		   &host, &channel, &id, &lun) != 4)
	    break;
	if (fgets(buf, sizeof(buf), f) == NULL)
	    break;
	if (strncmp(buf, "  Vendor:", 9))
	    break;
	if (fgets(buf, sizeof(buf), f) == NULL)
	    break;
	if (strncmp(buf, "  Type:   ", 10))
	    break;
	if (!strncmp(buf+10, "Direct-Access", 13)) {
	    if (disk >= sdlen) {
		hd = (struct sdsk_disk *)
		     realloc(hd, (hdlen+(disk&~3)+4)*sizeof(struct sdsk_disk));
		sd = hd + hdlen;
		memset (sd + sdlen, 0,
			((disk&~3)+4-sdlen)*sizeof(struct sdsk_disk));
		sdlen = (disk&~3)+4;
	    }
	    sd[disk].type = SDSK_TYPE_SD;
	    sd[disk].host = host;
	    sd[disk].hi = channel;
	    sd[disk].mid = id;
	    sd[disk].lo = lun;
	    disk++;
	}
    }
    fclose (f);

    if (!(dir = opendir("/proc/scsi"))) {
	if (!hdlen && hd) {
	    free(hd);
	    hd = NULL;
	}
	sd = NULL;
	sdlen = 0;
	return 1;
    }

    while ((ent = readdir(dir))) {
	if (!strcmp (ent->d_name, "scsi") || ent->d_name[0] == '.')
	    continue;
	sprintf (path, "/proc/scsi/%s", ent->d_name);
	if (stat (path, &st) < 0 || !S_ISDIR (st.st_mode))
	    continue;
	if (!(dirhba = opendir(path)))
	    continue;

	while ((enthba = readdir(dirhba))) {
	    if (enthba->d_name[0] == '.')
		continue;
	    host = atoi(enthba->d_name);
	    sprintf (path, "/proc/scsi/%s/%s", ent->d_name, enthba->d_name);
	    f = fopen (path, "r");
	    if (f == NULL) continue;

	    if (!strcmp (ent->d_name, "esp") ||
		!strcmp (ent->d_name, "qlogicpti") ||
		!strcmp (ent->d_name, "fcal"))
		p = "PROM node";
	    else if (!strcmp (ent->d_name, "pluto"))
		p = "serial ";
	    else
		p = "PCI bus";
	    while (fgets (buf, sizeof(buf), f) != NULL) {
		q = strstr (buf, p);
		if (q == NULL) continue;
		prom_node = 0;
		switch (p[1]) {
		case 'R':
		    if (sscanf (q, "PROM node %x", &prom_node) == 1)
			q = NULL;
		    break;
		case 'e':
		    if (sscanf (q, "serial 000000%x %*dx%*d on soc%*d port %x PROM node %x",
				&id, &lun, &prom_node) == 3 &&
			lun >= 10 && lun <= 11) {
			q = NULL;
		    }
		    break;
		case 'C':
		    if (sscanf (q, "PCI bus %x device %x", &pci_bus, &pci_devfn) == 2) {
			q = NULL;
			prom_node = prom_pci2node (pci_bus, pci_devfn);
		    }
		    break;
		}
		if (q == NULL) {
		    for (disk = 0; disk < sdlen; disk++)
			if (sd[disk].host == host && sd[disk].type) {
			    sd[disk].prom_node = prom_node;
			    if (p[1] == 'e') {
				sd[disk].type = SDSK_TYPE_PLN;
				sd[disk].lo = (lun << 28) | id;
			    } else if (!strcmp (ent->d_name, "fcal"))
				sd[disk].type = SDSK_TYPE_FC;
			}
		}
	    }
	    if (!strcmp (ent->d_name, "fcal")) {
		while (fgets (buf, sizeof(buf), f) != NULL) {
		    unsigned long long ll;
		    if (sscanf (buf, " [AL-PA: %*x, Id: %d, Port WWN: %Lx, Node WWN: ", &id, &ll) == 2) {
			for (disk = 0; disk < sdlen; disk++)
			if (sd[disk].host == host && sd[disk].mid == id) {
			    sd[disk].hi = ll >> 32;
			    sd[disk].mid = ll;
			}
		    }
		}
	    }
	    fclose(f);
	}
	closedir(dirhba);
    }
    closedir(dir);
    return 0;
}

static int get_prom_ver(void)
{
    FILE *f = fopen ("/proc/cpuinfo","r");
    int ver = 0;
    char buffer[1024];
    char *p;
                    
    if (f) {
	while (fgets (buffer, 1024, f)) {
	    if (!strncmp (buffer, "promlib", 7)) {
		p = strstr (buffer, "Version ");
		if (p) {
		    p += 8;
		    if (*p == '0' || (*p >= '2' && *p <= '3')) {
			ver = *p - '0';
		    }
		}
		break;
	    }
	}
	fclose(f);
    }
    if (!ver) {
	int len;
        p = prom_getopt("sd-targets", &len);
        if (p && len > 0 && len <= 8)
	    strcpy(sd_targets, p);
    }
    return ver;
}

static void check_aliases(void) {
    int nextnode, len;
    char *prop;
    hasaliases = 0;
    for (nextnode = prom_getchild(prom_root_node); nextnode; nextnode = prom_getsibling(nextnode)) {
	prop = prom_getproperty("name", &len);
	if (prop && len > 0 && !strcmp (prop, "aliases"))
	    hasaliases = 1;
    }
}

char *prom_root_name = NULL;

static void get_root_name(void) {
    int len;
    char *prop;
    
    prom_getsibling(0);
    prop = prom_getproperty("name", &len);
    if (prop && len > 0)
	prom_root_name = strdup(prop);
}

int init_sbusdisk(void) {
    if (prom_init(O_RDONLY))
	return -1;
    promvers = get_prom_ver();
    check_aliases();
    get_root_name();
    scan_ide();
    scan_scsi();
    prom_walk_callback = scan_walk_callback;
    prom_walk(prom_path, prom_root_node, prom_getchild (prom_root_node), 0);
    close(promfd);
    return 0;
}

void set_prom_vars(char *linuxAlias, char *bootDevice) {
    int len;
    int aliasDone = 0;
    if (prom_init(O_RDWR))
	return;
    if (linuxAlias && hasaliases) {
	char *use_nvramrc;
	char nvramrc[2048];
	char *p, *q, *r, *s;
	int enabled = -1;
	int count;

	use_nvramrc = prom_getopt ("use-nvramrc?", &len);
	if (len > 0) {
	    if (!strcasecmp (use_nvramrc, "false"))
		enabled = 0;
	    else if (!strcasecmp (use_nvramrc, "true"))
		enabled = 1;
	}
	if (enabled != -1) {
	    p = prom_getopt ("nvramrc", &len);
	    if (p) {
		memcpy (nvramrc, p, len);
		nvramrc [len] = 0;
		q = nvramrc;
		for (;;) {
		    /* If there is already `devalias linux /some/ugly/prom/path'
		       make sure we fully understand that and remove it. */
		    if (!strncmp (q, "devalias", 8) && (q[8] == ' ' || q[8] == '\t')) {
			for (r = q + 9; *r == ' ' || *r == '\t'; r++);
			if (!strncmp (r, "linux", 5)) {
			    for (s = r + 5; *s && *s != ' ' && *s != '\t'; s++);
			    if (!*s) break;
			    if (s == r + 5 ||
				(r[5] == '#' && r[6] >= '0' && r[6] <= '9' &&
				 (s == r + 7 ||
				  (r[7] >= '0' && r[7] <= '9' && s == r + 8)))) {
				for (r = s + 1; *r == ' ' || *r == '\t'; r++);
				for (; *r && *r != ' ' && *r != '\t' && *r != '\n'; r++);
				for (; *r == ' ' || *r == '\t'; r++);
				if (*r == '\n') {
				    r++;
				    memmove (q, r, strlen(r) + 1);
				    continue;
				}
			    }
			}
		    }
		    q = strchr (q, '\n');
		    if (!q) break;
		    q++;
		}
		len = strlen (nvramrc);
		if (len && nvramrc [len-1] != '\n')
		    nvramrc [len++] = '\n';
		p = nvramrc + len;
		p = stpcpy (p, "devalias linux ");
		r = linuxAlias;
		q = strchr (r, ';');
		count = 1;
		while (q) {
		    memcpy (p, r, q - r);
		    p += q - r;
		    sprintf (p, "\ndevalias linux#%d ", count++);
		    p = strchr (p, 0);
		    r = q + 1;
		    q = strchr (r, ';');
		}
		p = stpcpy (p, r);
		*p++ = '\n';
		*p = 0;
		prom_setopt ("nvramrc", nvramrc);
		if (!enabled)
		    prom_setopt ("use-nvramrc?", "true");
		aliasDone = 1;
	    }
	}
    }
    if (bootDevice) {
	char *p;
	if (aliasDone)
	    bootDevice = "linux";
	p = prom_getopt ("boot-device", &len);
	if (p) {
	    prom_setopt ("boot-device", bootDevice);
	    prom_setopt ("boot-file", "");
	} else {
	    p = prom_getopt ("boot-from", &len);
	    if (p)
		prom_setopt ("boot-from", bootDevice);
	}
    }
    close(promfd);
}

#ifdef STANDALONE_SILO

int main(void) {
    int i;

    init_sbusdisk();
    set_prom_vars ("/sbus@1f,0/espdma/esp/sd@1,0:c;/sbus@1f,0/espdma/esp/sd@1,0:g;/sbus@1f,0/espdma/esp/sd@1,0:h", "linux");
    printf ("prom root name `%s'\n", prom_root_name);
    for (i = 0; i < hdlen; i++) {
	if (hd[i].type)
		printf ("hd%c %x %d %d %d\n", i + 'a', hd[i].prom_node,
						    hd[i].hi, hd[i].mid, hd[i].lo);
	if (hd[i].prom_name) printf ("%s\n", hd[i].prom_name);
    }
    for (i = 0; i < sdlen; i++) {
	if (sd[i].type) {
	    if (i < 26)
		printf ("sd%c %x %d %d %d\n", i + 'a', sd[i].prom_node,
						    sd[i].hi, sd[i].mid, sd[i].lo);
	    else
		printf ("sd%c%c %x %d %d %d\n", (i / 26) + 'a' - 1, (i % 26) + 'a', sd[i].prom_node,
						    sd[i].hi, sd[i].mid, sd[i].lo);
	}
	if (sd[i].prom_name) printf ("%s\n", sd[i].prom_name);
    }
    exit(0);
}

#else

#include <Python.h>

static PyObject *disk2PromPath (PyObject *, PyObject *);
static PyObject *zeroBasedPart (PyObject *, PyObject *);
static PyObject *hasAliases (void);
static PyObject *promRootName (void);
static PyObject *setPromVars (PyObject *, PyObject *);

static PyMethodDef _siloMethods[] = {
    { "disk2PromPath", disk2PromPath, 1 },
    { "hasAliases", hasAliases, 1 },
    { "promRootName", promRootName, 1 },
    { "zeroBasedPart", zeroBasedPart, 1 },
    { "setPromVars", setPromVars, 1 },
    { NULL, NULL }
};

void
init_silo ()
{
    PyObject *m;
    m = Py_InitModule ("_silo", _siloMethods);

    if (init_sbusdisk ())
	Py_FatalError ("unable to open /dev/openprom");
    if (PyErr_Occurred ())
	Py_FatalError ("can't initialize module _silo");
}

static PyObject *
disk2PromPath (PyObject *self, PyObject *args)
{
    unsigned char *disk, prompath[1024];
    int diskno = -1, part;

    if (!PyArg_ParseTuple (args, "s", &disk))
	return NULL;
    if (disk[0] == 'h' && disk[1] == 'd' && disk[2] >= 'a' && disk[2] <= 'z') {
	diskno = disk[2] - 'a';
	disk += 3;
    } else if (disk[0] == 's' && disk[1] == 'd' && disk[2] >= 'a' && disk[2] <= 'z') {
	if (disk[3] >= 'a' && disk[3] <= 'z') {
	    diskno = (disk[2] - 'a' + 1) * 26 + (disk[3] - 'a');
	    disk += 4;
	} else {
	    diskno = disk[2] - 'a';
	    disk += 3;
	}
	if (diskno >= 128)
	    diskno = -1;
	else
	    diskno += hdlen;
    }
    if (diskno == -1)
	part = -1;
    else if (!disk[0])
	part = 3;
    else {
	part = atoi (disk);
	if (part <= 0 || part > 8) part = -1;
    }
    if (diskno < 0 || part == -1 ||
	diskno >= hdlen + sdlen || !hd[diskno].prom_name) {
	Py_INCREF(Py_None);
	return Py_None;
    }
    if (!promvers)
	sprintf (prompath, "%s%d)", hd[diskno].prom_name, part ? part - 1 : 2);
    else {
	if (part)
	    sprintf (prompath, "%s:%c", hd[diskno].prom_name, part + 'a' - 1);
	else
	    strcpy (prompath, hd[diskno].prom_name);
    }
    return Py_BuildValue ("s", prompath);
}

#include "../balkan/balkan.h"
#include "../balkan/sun.h"

static PyObject *
zeroBasedPart (PyObject *self, PyObject *args)
{
    unsigned char *disk;
    int part = 3, fd, i;
    struct partitionTable table;

    if (!PyArg_ParseTuple (args, "s", &disk))
	return NULL;

    fd = open(disk, O_RDONLY);
    if (fd < 0) return NULL;
    if (sunpReadTable(fd, &table)) {
	close(fd);
    	return NULL;
    }
    if (table.parts[2].type == -1 || table.parts[2].startSector) {
	for (i = 0; i < 8; i++) {
	    if (table.parts[i].type == -1) continue;
	    if (!table.parts[i].startSector) {
		part = i + 1;
		break;
	    }
	}
    }
    close(fd);
    return Py_BuildValue ("i", part);
}

static PyObject *
hasAliases (void)
{
    return Py_BuildValue ("i", hasaliases);
}

static PyObject *
promRootName (void)
{
    return Py_BuildValue ("s", prom_root_name ? prom_root_name : "");
}

static PyObject *
setPromVars (PyObject *self, PyObject *args)
{
    char *linuxAlias, *bootDevice;
    if (!PyArg_ParseTuple (args, "ss", &linuxAlias, &bootDevice))
	return NULL;
    if (linuxAlias && !*linuxAlias) linuxAlias = NULL;
    if (bootDevice && !*bootDevice) bootDevice = NULL;
    set_prom_vars (linuxAlias, bootDevice);
    Py_INCREF(Py_None);
    return Py_None;
}

#endif
