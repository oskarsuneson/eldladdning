# ELDLEDNINGSCENTRAL // Iron Nest-stil

Ett artillerispel för terminalen i WarGames-stil (grönt på svart). Du sitter vid en
artilleripjäs och får **exakta underrättelser** om vad och var du ska skjuta. FDC
(eldledningscentralen) räknar ut riktning, lutning och laddning åt dig så att granaten landar
**exakt där du vill** – men vinden är inte exakt uppmätt, så du måste skjuta in dig.
Slå ut alla mål utan att träffa egna trupper.

Fungerar på **Linux, macOS och Windows**. Ingen internetanslutning behövs.

## Funktioner

- **Exakt eldledning:** `PUNKT A` räknar ut AZ, EL och LAD så att granaten landar på mål A
  (vind inräknad). Du kan också landa på valfria koordinater eller med en offset från ett mål
- **Exakt information:** koordinater, avstånd och azimut med decimaler, beräknat nedslag, flygtid och spridning
- **Inskjutning med `KORR`:** vindmätningen har ett okänt fel. Ett observerat nedslag låter FDC räkna ut det verkliga vindfelet – fler nedslag ger säkrare värde
- **Bläddra mellan mål** med `TAB` / `SHIFT+TAB`, pilarna eller `NASTA` / `FORRA`
- Flera mål (A–D) per uppdrag, ibland tätt ihop så att en granat kan träffa flera
- **Fem granater:** `HE`, `APHE`, `FRAG` (enorm radie, nästan ingen skada mot pansar), `HEAT` (måste träffa exakt, slår ut allt i ett skott) och `LJUS` (belyser området och avslöjar fiender)
- **Okända kontakter:** dolda bonusmål som bara syns när de belyses av LJUS (eller sprängs av splitter)
- Måltyper: infanteri, lastbilskolonner, pansar, bunkrar, radar, artilleribatterier m.fl.
- Utan **spejare** syns varken mål eller nedslag på kartan; spejare köps i **butiken** med poäng. LJUS fungerar som alternativ
- Butik med uppgraderingar (extra granater, precisionsoptik, fast spejare, förtroende)
- Din progress **sparas automatiskt** mellan spelomgångar
- Inbyggd **tutorial** som visas vid varje start (klicka eller tryck ENTER för att bläddra, pil upp/ner för att scrolla, `S` för att hoppa över, `?` för att öppna den igen, `TUTORIAL AV` för att stänga av)

## Kom igång

Du behöver Python 3.9 eller nyare (på Windows 3.9–3.13, se nedan) och en terminal som är minst **110 tecken bred och 30 rader hög**
(maximera fönstret om spelet ber dig göra det större).

### Linux

```bash
python3 eldledning.py
```

Eller kör startfilen, som kontrollerar Python och gör fönstret större:

```bash
sh start_linux.sh
```

(Eller `chmod +x start_linux.sh` en gång och sedan `./start_linux.sh`.)

### macOS

```bash
python3 eldledning.py
```

Standardfönstret i Terminal är litet – dra ut det eller kör i helskärm.

Eller dubbelklicka på **`start_mac.command`** i Finder – den gör fönstret större och startar spelet.
Första gången kan macOS blockera filen: högerklicka → **Öppna** → **Öppna**. Om det står
*"permission denied"* (det händer när filen laddats upp via webben och tappat sin körrättighet),
kör `chmod +x start_mac.command` i Terminal, eller starta med `sh start_mac.command`.

### Windows (PowerShell eller Windows Terminal)

Windows saknar Pythons `curses`-modul, så den installeras med paketet `windows-curses`.
Det paketet finns än så länge bara för **Python 3.9–3.13** – inte för 3.14/3.15.

**1. Installera Python 3.13** (om du har en nyare Python; den påverkar inte din vanliga):

```powershell
winget install Python.Python.3.13
```

Stäng och öppna PowerShell igen efteråt.

**2. Ladda ner och packa upp spelet.** Tryck på **Code → Download ZIP** här på GitHub och
packa upp zip-filen (högerklicka → *Extract All*).

**3. Starta spelet – det enklaste sättet:** öppna den uppackade mappen och dubbelklicka på
**`start_windows.bat`**. Den hittar själv en fungerande Python, installerar `windows-curses`
vid behov och startar spelet.

**Eller starta från PowerShell:** gå först till den uppackade mappen med `cd` (mappnamnet
beror på vad repot heter – skriv `dir` för att se vad som finns, och du ska se `eldledning.py`
i listan när du står rätt). Kör sedan, ett kommando i taget:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 eldledning.py
```

Har du redan Python 3.9–3.13 som standard fungerar `python` i stället för `py -3.13`.

Gör fönstret stort (minst 110×30) innan du startar.

## Så spelar du

1. Läs målen överst: skydd, koordinater (O = öst, N = norr), avstånd och azimut.
   Bläddra mellan målen med `TAB`.
2. Låt FDC räkna ut lösningen och skjut:

   ```
   PUNKT A HE ELD
   ```

3. Titta på rapporten (spejaren, eller den belysta kartan efter `LJUS`). Skriv `KORR` så räknar
   FDC ut vindfelet och rättar lösningen. Vindkorrigeringen gäller **hela uppdraget**, så nästa mål
   blir också mer exakt.
4. Välj rätt granat och skjut igen – `HEAT` kräver att du träffar inom 10 m.
5. Slå ut alla mål innan granaterna tar slut. Träffa aldrig egna trupper (`#`).

**Så träffar du exakt:** `PUNKT A` → ett inskjutningsskott (`HE`, eller `LJUS` om du saknar
spejare) → `KORR` → (gärna ett till) → `HEAT`. Två inskjutningsskott räcker oftast för att
HEAT ska träffa nästan varje gång även på 5 km.

### Kommandon

| Kommando | Vad det gör |
|---|---|
| `MAL A` | Välj mål (A–F) |
| `TAB` / `SHIFT+TAB`, `NASTA` / `FORRA` | Bläddra till nästa / föregående mål (pil höger/vänster fungerar på tom rad) |
| `PUNKT A` | FDC räknar ut AZ, EL och LAD så att granaten landar exakt på mål A (vind inräknad). Utan namn: valt mål |
| `PUNKT A 30 -10` | Samma, men 30 m öst och 10 m söder om mål A (öst +, norr +) |
| `PUNKT 3375 2328` | Landa på exakta koordinater (öst norr, i meter) |
| `AZ 28.35` | Azimut manuellt (0 = norr, 90 = öst), decimaler går bra |
| `EL 41.72` | Elevation manuellt, 5–85 grader – styr hur långt granaten flyger |
| `LAD 2` | Laddning 1–3 (`PUNKT` väljer själv om du inte valt) |
| `HE` / `APHE` / `FRAG` / `HEAT` / `LJUS` | Välj granat |
| `ELD` | Skjut |
| `KORR` | Räknar om lösningen från senaste observerade nedslag (spejare eller LJUS) |
| `BUTIK` | Öppna/stäng butiken; `KOP 1` köper vara nummer 1 |
| `SPARA` | Spara direkt (sker även automatiskt) |
| `?` | Visa tutorialen igen (tryck `?` på tom rad; `TUTORIAL` och `HJALP` fungerar också) |
| `TUTORIAL AV` / `TUTORIAL PA` | Stäng av / sätt på att tutorialen visas automatiskt vid start |
| `NOLLSTALL JA` | Radera all sparad progress |
| `Q` | Spara och avsluta |

Flera kommandon går att skriva på samma rad, t.ex. `PUNKT A HEAT ELD`.

### Granater

| Typ | Radie | Oskyddat | Pansar | Bunker | Säkerhetsavstånd | Per uppdrag* |
|---|---|---|---|---|---|---|
| `HE` | 60 m | 100 % | 25 % | 15 % | 100 m | 6 |
| `APHE` | 30 m | 40 % | 100 % | 60 % | 70 m | 5 |
| `FRAG` | 150 m | 70 % | 3 % | 1 % | 170 m | 3 |
| `HEAT` | 10 m | 100 % | 100 % | 100 % | 25 m | 2 |
| `LJUS` | 700 m | – | – | – | – | 3 |

\* Plus extra granater för varje ytterligare mål och uppgraderingar från butiken.

- **FRAG** har enorm radie men gör nästan ingen skada mot pansar och bunkrar.
- **HEAT** måste träffa inom 10 m men slår ut vad som helst i ett skott. Den har också minst spridning.
- **LJUS** gör ingen skada. Den belyser området på kartan, visar vilka fiender som finns i närheten
  (med exakta koordinater) och avslöjar okända kontakter. Nedslaget syns alltid, så du kan `KORR`:a på det
  även utan spejare.

## Sparfil

Progress sparas i `.eldledning_save.json` i din hemmapp (`~` på Linux/macOS,
`C:\Users\<namn>` på Windows). Radera filen eller skriv `NOLLSTALL JA` för att börja om.

## Utveckling och tester

```bash
python3 -m unittest discover -s tests -v
```

GitHub Actions kör testerna på Ubuntu, macOS och Windows (se `.github/workflows/test.yml`).

## Felsökning

- **"Gör terminalen större"** – maximera fönstret (minst 110×30).
- **Windows: `No matching distribution found for windows-curses`** – din Python är för ny (3.14/3.15). Installera Python 3.13 och kör med `py -3.13` (se Windows ovan).
- **Windows: `No module named '_curses'`** – kör `py -3.13 -m pip install windows-curses`.
- **`Could not open requirements file` / `can't open file 'eldledning.py'`** – du står i fel mapp. Gå först till mappen med spelets filer (`cd` till den, kontrollera med `dir`).
- **Tecken ser konstiga ut** – spelet använder bara ASCII, men prova Windows Terminal i stället för gamla cmd.exe.

## Licens

MIT – se [LICENSE](LICENSE).
