
                      09Hilfe zu Kernel-Parametern07

Sie k”nnen einige Kernel-Parameter von der Befehlszeile aus eingeben. Diese
Parameter werden dann an den zu startenden Kernel bergeben. Hierzu z„hlen
jedoch keine Optionen fr Module wie Ethernet-Karten oder Ger„te wie
CD-ROM-Laufwerke.

Um eine Option an den Kernel zu bergeben, verwenden Sie das folgende Format:
     0flinux <Optionen>07
Wenn Sie einen anderen Installationsmodus verwenden m”chten, geben Sie diesen
nach den Optionen an.

Um beispielsweise auf einem System mit 128 MB RAM eine Installation im
Expertenmodus durchzufhren, geben Sie folgenden Befehl ein:
     0flinux mem=128M expert07

Um Optionen an Module zu bergeben, mssen Sie den Expertenmodus verwenden,
da in diesem Modus die automatische Erkennung von Ger„ten am PCI-Bus nicht
aktiviert ist. Wenn Sie vom Installationsprogramm nach dem Ger„tetyp gefragt
werden, dem Sie Optionen oder Parameter bergeben m”chten, geben Sie diese
einfach in das hierfr vorgesehene Feld ein. 

05[F1-Hauptbildschirm] [F2-Allgemein] [F3-Expertenmodus] [F4-Kernel] [F5-Rettung]07
