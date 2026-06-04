# Popis zariadenia

ROCKPro64 je single board počítač vyrobený PINE64. PINE64 je spoločnosť zameraná na tvorbu single board počítačov na 64 bitovej architektúre ARM a novodobo RISC-V.
Teda ide o podobné zariadenia ako Raspberry/Orange Pi. Feature set tohto zariadenia je taktiež podobný raspberry atď. Malo by ísť o najvýkonnejšie PINE64 zariadenie.

Zariadenie obsahuje:
- 6 CPU cores : 4 core ARM Cortex A53 + 2 core ARM Cortex A72
- ARM Mali T860 MP4 GPU (podobný výkon ako 2014-15 desktop GPU)
- max 4GB RAM
- Gigabit ethernet
- Micro SD slot
- eMMC modul slot (embeded multimedia)
- SPI Flash 128Mbit
- 4K digital video out
<hr>

- USB 2x 2.0 + 1x 3.0 + 1x USB-C
- PCIe 4x slot
- 40 GPIO pinov
- 12V 3A/5A barrel port
- 3.5mm audio jack with mic input
- množstvo ďalších portov na periférie, moduly a komunikáciu
<hr>

<img src="https://pine64.org/devices/images/rockpro64.jpg">

# OS 

Na zariadenie bol inštalovaný operačný systém DietPi, ide o optimalizovaný minimálny Debian. Tento OS poskytuje inštalátory
navrhnuté priamo na určité single board počítače ako sú:
- Raspberry Pi
- Odroid
- PINE64
- Radxa
- Asus Tinker Board
- Nano Pi
- Orange Pi
- RISC-V Star64 / VisionFive 2
- PC / VM pre beh na desktope

<img width="666" height="444" alt="image" src="https://github.com/user-attachments/assets/f6c2c5c7-8048-4852-8aea-827209f9c518" />
CLI poskytuje možnosti jednoduchšie updatovať a inštalovať softvér a ďalšie iné konfiguračné možnosti. 

# Docker
Deployment aplikácii je riešený cez docker. Je to spravené preto, aby prípadné chyby v kóde nespôsobili pád celého systému,
a aby mohol aj nepriviléhgovaný používateľ používať kontainerizovaný python kontainer s plnými privilégiami. Cez docker bol
na začiatku deploynuty python kontainer, phpmyadmin a mysql databáza.

# Tailscale
Na prístup k servéru používajú programátori Tailscale. Ide o platformu, ktorá medzi prihlásenými zariadeniami vytvára
zabezpečenú internetovú komunikáciu a priraďuje statické IP adresy. Platforma je využívaná najmä pre IoT/homelab zariadenia,
funguje kvázi ako VPN. 
