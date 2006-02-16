#ifndef SMP_H
#define SMP_H

extern int detectSMP(void);
extern int detectHT(void);
extern int detectCoresPerPackage(void);
extern int detectSummit(void);

#endif /* SMP_H */
