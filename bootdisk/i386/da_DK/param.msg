

                        09Hjælp for kerneparametere07

Nogen kerneparametre kan specificeres på kommandolinjen og vil derfra blive
sendt videre til kernen. Dette omfatter ikke alternativer for moduler for
enheder som netværkskort eller CD-RPM enheder.

For at sende et flag til kernen bruger du følgende format:
     0flinux <flag>07
Hvis en speciel installationstype er ønsket, så skriv den ind efter flagene.

For eksempel, for at installere et system med 128MB RAM i ekspert-modus,
skriv følgende:
     0flinux mem=128M expert07

For at give flag til moduler skal du starte ekspert-modus for at deaktivere
PCI-autosøgning. Når instalationsprogrammet spørger dig efter enhedstype som
behøver et flag eller en parameter, vil du få muligheden for at opgive disse
der og da. 



05[F1-Hoved] [F2-Generelt] [F3-Ekspert] [F4-Kjerne] [F5-Redning]07
