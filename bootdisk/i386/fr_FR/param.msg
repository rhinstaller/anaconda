

                        09Aide sur le paramétrage du noyau07

Il est possible de spécifier certains paramètres du noyau dans la ligne de
commande ; ils seront transmis au noyau en fonctionnement. Ceux-ci n'incluent
pas d'options pour les modules tels que les cartes ethernet ou les périphériques
tels que les lecteurs de CD-ROM.

Pour transmettre une option au noyau, utilisez le format suivant :
     0f<options> linux07
Si vous souhaitez un autre mode d'installation, entrez-le après les options.

Par exemple, pour effectuer une installation sur un système disposant de
128 Mo de RAM en mode expert, entrez ce qui suit :
     0flinux mem=128M expert07

Pour transmettre des options à des modules, utilisez le mode expert afin de
désactiver l'autodétection PCI. Lorsque le programme d'installation demande
quel est le type de périphérique nécessitant le transfert d'une option ou
d'un paramètre, un espace est prévu pour les y insérer. 



05[F1-Principal] [F2-Général] [F3-Expert] [F4-Noyau] [F5-Secours]07

