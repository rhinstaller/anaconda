#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vbe.h"
#ident "$Id$"

int main(int argc, char **argv)
{
	int i, j;
	unsigned char hmin = -1, hmax = -1, vmin = -1, vmax = -1;
	if(argc < 2) {
		char *p = argv[0];
		if(strchr(p, '/')) {
			p = strchr(p, '/');
			p++;
		}
		fprintf(stderr,"syntax: %s [-hsync] [-vsync] [-modelines]\n",p);
		exit(1);
	}
	for(i = 1; i < argc; i++) {
		if((strcmp(argv[i], "-hsync") == 0) ||
		   (strcmp(argv[i], "-vsync") == 0)) {
			vbe_get_edid_ranges(&hmin, &hmax, &vmin, &vmax);
			if(!hmin && !hmax && !vmin && !vmax) {
				struct vbe_modeline* modelines;
				modelines = vbe_get_edid_modelines();
				for(j = 0;
				    modelines && (modelines[j].refresh != 0);
				   j++) {
					if(hmin == 0) hmin = modelines[j].hfreq;
					/* guess */
					if(modelines[j].hfreq)
					hmin = (hmin < modelines[j].hfreq) ?
					        hmin : modelines[j].hfreq;
					if(modelines[j].hfreq)
					hmax = (hmax > modelines[j].hfreq) ?
					        hmax : modelines[j].hfreq;
					if(vmin == 0) vmin = modelines[j].vfreq;
					if(modelines[j].vfreq)
					vmin = (vmin < modelines[j].vfreq) ?
					        vmin : modelines[j].vfreq;
					if(modelines[j].vfreq)
					vmax = (vmax > modelines[j].vfreq) ?
					        vmax : modelines[j].vfreq;
				}
			}
		}
		if(strcmp(argv[i], "-hsync") == 0) {
			printf("%d-%d\n", hmin, hmax);
		}
		if(strcmp(argv[i], "-vsync") == 0) {
			printf("%d-%d\n", vmin, vmax);
		}
		if(strcmp(argv[i], "-modelines") == 0) {
			struct vbe_modeline* modelines;
			modelines = vbe_get_edid_modelines();
			for(j=0; modelines && (modelines[j].refresh != 0); j++){
				if(modelines[j].modeline) {
					printf("# %dx%d, %1.1f%sHz; hfreq=%f, vfreq=%f\n%s\n",
					       modelines[j].width,
					       modelines[j].height,
					       modelines[j].refresh,
					       modelines[j].interlaced?"i":"",
					       modelines[j].hfreq,
					       modelines[j].vfreq,
					       modelines[j].modeline);
				}
			}
			if(modelines) {
				free(modelines);
			} else {
				return 1;
			}
		}
	}
	return 0;
}
