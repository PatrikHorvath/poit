# Flask verejná adresa

Pre vývojára je zabezpečený prístup pomocou Tailscale na pot na **porte 8888, pozor v app.py, treba deployovat na port 5000**. Vývojár sa adresou `http://100.94.58.105:8888` dokáže pripojiť na endpointy Flask inštancie.

Pre iného používateľa, napríklad ak chceme posielať dáta z Arduino, tak je potrebné, aby bol port 8888 zverejnený, čo je možné iba pri plnom prístupe na servér, viem to spúšťať iba JA, kontaktujte ma ak je potrebné to sprístupniť. Po sprístupnení bude prístupná adresa `https://dietpi.tailfa8c79.ts.net/`, ktorá je presmerovaná na port 8888.

# Development

Na adrese 2222 je dostupný SSH access do kontaineru s pythonom. Taktiež prístupné iba vývojárovi. Tu vývojár spúšťa `app.py` a pripadne inštaluje python knižnice.

Príkaz na pripojenie `ssh -p 2222 devuser@100.94.58.105`, heslo v DM. V prípade, že sa vykonajú zmeny na kontaineri je možné, že dostaneme výpis:
```
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
```

V takom prípade je potrebné vymazať existujúci fingerprint pre `devuser@100.94.58.105` a skusiť sa pripojiť znovu. 

# VSCODE návod
1. Ľavý spodný roh ikonka ><
2. Connect to Host
3. Add new SSH host -> `ssh -p 2222 devuser@100.94.58.105`
4. Možno treba prijať fingerprint
5. Budeme 2x promptnutý na heslo
6. Počkať na inštaláciu vscode-server pluginu
7. Otvoriť directory -> `/home/devuser`
8. `git fetch --all`
9. `git checkout server`  (možno --force)
10. `git pull`

# Prístup na databázu
Databáza je dostupná na porte 8080 pomocou PhpMyAdmin. Prístup je riešený iba cez Tailscale, teda je to ošetrené tak, že prístup má iba vývojár na adrese `http://100.94.58.105:8080`.

Vývojár Flasku musí pridať súbor `config.cfg` na uloženie hesla databázy a ostatných info.
