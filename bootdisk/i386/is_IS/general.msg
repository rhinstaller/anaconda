
                        09Almenn ræsihjálp07

Þú ert núna tilbúin(n) til að hefja uppsetninguna. Í flestum tilfellum
er best að fara af stað með því að einfaldlega slá á 0f<ENTER>07 hnappinn.

Myndræna uppsetningarforritið notar framebuffer í 16 bita litum og 800x600
upplausn. Ef þú ert í vandræðum með myndræna uppsetningarforritið getur
þú reynt einn af eftirfarandi rofum:
    -  Til að ræsa uppsetningu í upplausninni 640x480, slá inn 0flowres <ENTER>07.
    -  Nota ekki framebuffer ham með því að slá inn 0fnofb <ENTER>07.
    -  Prófa aðrar upplausnir með því að bæta við 'vga=xxx' skv. eftirfarandi:
         1024x768x8bpp  -> vga=773        1024x768x16bpp  -> vga=791 
         1280x1024x8bpp -> vga=775        1280x1024x16bpp -> vga=794

Á sumum tölvum veldur sjálfvirka leitin að vélbúnaði og stillingum hans 
vandamálum í uppsetningu. Ef þú lendur í vandræðum í uppsetingu getur þú
byrjað upp á nýtt í sérfræðingsham.   Sláðu á 05<F3>07 fyrir frekari
upplýsingar um sérfræðingsham.

Það er einnig hægt að gefa Linux kjarnanum talsvert af rofum við ræsingu.
Sláðu á 05<F4>07 fyrir frekari upplýsingar.


05[F1-Main] [F2-General] [F3-Expert] [F4-Kernel] [F5-Rescue]07
