# Flask verejná adresa

Zatial nie je nastavené, aby vebstránky flask boli verejne dostupné. PC, ktorý má nastavený Tailscale sa dokáže pripojiť na **porte 8888, pozor v app.py, treba deployovat na port 5000**.

Aktuálne dostupné cez Tailscale http://100.94.58.105:8888 po deploynutí app.py

# Development

Na adrese 2222 je dostupný SSH access do kontaineru s pythonom.

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
