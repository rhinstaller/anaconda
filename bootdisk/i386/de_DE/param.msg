

                     09Kernel-Parameter-Hilfe07

Einige Kernel-Parameter k”nnen an der Kommandozeile angegeben werden, die
dann dem laufenden Kernel bergeben werden. Parameter fr Module (wie z.B.
Ethernet-Karten oder CD-ROM-Laufwerke) k”nnen nicht bergeben werden.

Um den Kernel mit Parametern zu starten, benutzen Sie das folgende Format:
     0flinux <Parameter>07
Wenn ein anderer Modus gebraucht wird, geben Sie ihn nach den Parametern
an.

Um zum Beispiel ein System mit 128 MB RAM im Expertenmodus zu starten,
verwenden Sie:
     0flinux mem=128M expert07

Um Parameter an Module zu bergeben, mssen Sie den Expertenmodus verwenden,
um die PCI Hardwareerkennung abzuschalten. Wenn die Installation nach dem 
Ger„tetyp fragt, der einen Parameter braucht, k”nnen die Parameter 
dann eingegeben werden.


05[F1-Hauptmen] [F2-Generelles] [F3-Experten] [F4-Kernel] [F5-Rettung]07
