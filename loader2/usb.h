#ifndef H_USB
#define H_USB

extern int usbInitialize(moduleList modLoaded, moduleDeps modDeps,
		  moduleInfoSet modInfo);
extern void usbInitializeMouse(moduleList modLoaded, moduleDeps modDeps,
                        moduleInfoSet modInfo);
extern void sleepUntilUsbIsStable(void);

#endif
