

                      09Aide sur les paramŠtres du noyau07

 A partir de la ligne de commande, on peut donner certains paramŠtres au noyau 
 qui seront pass‚s … celui-ci. Cela ne concerne pas les options des modules 
 comme les cartes Ethernet ou les p‚riph‚riques comme les lecteurs de CD-ROM.

 Pour passer une option au noyau, utilisez la syntaxe suivante :
     0flinux <options>07
 Si vous d‚sirez un autre mode d'installation, pr‚cisez-le aprŠs les options.

 Par exemple, pour faire une installation sur un systŠme ayant 128 Mo de RAM 
 en utilisant le mode expert, entrez la ligne suivante :
     0flinux mem=128M expert07

 Pour passer des options aux modules, vous devrez utiliser le mode expert afin 
 de d‚sactiver la d‚tection PCI automatique. Lorsque l'on vous demandera quel 
 type de p‚riph‚rique a besoin d'une option ou quel paramŠtre il faut passer, 
 vous aurez de la place pour entrer ces informations … ce moment l….


05[F1-Principal] [F2-G‚n‚ral] [F3-Expert] [F4-Noyau] [F5-Secours]07
