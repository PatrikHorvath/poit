# POIT
Arduino kód + Raspberry backend/frontend pre vizualizáciu regulácie Peltier

Prosím necommitujte heslá, teda .env súbory atď, hodte si to do .gitignore 

# Pokyny GIT 
Predpokladáme podobný workflow ako pri zadaní WEBTE2
<img width="930" height="1110" alt="image" src="https://github.com/user-attachments/assets/ca19d434-5be5-4499-b604-2b30b7f0f321" />

1. Kód bude mať 2 hlavné branche Arduino / Server
2. Na Arduino branchi bude maintainovany kod pre Arduino, na server branchi kód pre vizualizáciu a správu servéru
3. Pri pridávaní zmien vytvárajte vlastný nový branch, ktorý sa pri dokončení funkcionality Pull Requestne a Mergne do branch Arduino/Server

# Základné príkazy
```git
git fetch --all
git branch                      (displays branches)
git branch name                 (new branch with name, CLONES CURRENT switched branch)
git branch -d branchName        (delete branch, do this after merging into arduino/server)
                                make sure to also delete branch on github in the merge request menu
git switch branchName           (or checkout branchName)

use github desktop or vscode source control to stage/unstage commits and commit

git pull                        (optional --all)
git push
git push origin branchName
```

# Dokumentácie
Ak je to applicable alebo dosť podstatné pre to čo ste vykonali, tak si spravte z master branche novu branch a pridajte nejaký `nazov_dokumentacie.md`, nech sa nakoniec z toho môže čerpať na dokumentáciu. Ideálne keď chcete napísať tak rovno v browseri kliknite na ADD FILE keď ste vo vetve MAIN a vo folderi DOCUMENTS

# Prvotné rozdelenie práce
- Patrik Horváth
- Matej Ištok
> práca na servéri

- Samuel Múdry 👑
- Michal Gregorovič
- Hai Nguyen Viet
> práca so zariadením

# Spisovanie kto čo spravil
Asi napíšte na Samovi alebo do spoločného chatu
