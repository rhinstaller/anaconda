
struct pciDevice {
        unsigned int vendor, device, type;
        char * driver;
        char * desc;
};

int probePciReadDrivers(const char *fn);
struct pciDevice **probePci(unsigned int type, int all);
