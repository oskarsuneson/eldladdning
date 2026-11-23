# ELDLEDNINGSCENTRAL // Iron Nest-stil

Ett artillerispel för terminalen i WarGames-stil (grönt på svart). Du sitter vid en
artilleripjäs och får **underrättelser** om vad och var du ska skjuta. Du räknar ut
riktning, lutning och laddning, väljer granat, skjuter, tolkar spejarens rapport och
justerar tills alla mål är utslagna – utan att träffa egna trupper.

Fungerar på **Linux, macOS och Windows**. Ingen internetanslutning behövs.

## Funktioner

- Flera mål (A–D) per uppdrag, ibland tätt ihop så att en granat kan träffa flera
- Olika granater: **HE** (stor radie, bra mot oskyddat) och **APHE** (pansarbrytande, bra mot pansar och bunkrar)
- Måltyper: infanteri, lastbilskolonner, pansar, bunkrar, radar, artilleribatterier m.fl.
- Vind och spridning – första skottet landar sällan exakt
- Utan **spejare** syns varken mål eller nedslag på kartan; spejare köps i **butiken** med poäng
- Butik med uppgraderingar (extra granater, precisionsoptik, fast spejare, förtroende)
- Din progress **sparas automatiskt** mellan spelomgångar
- Inbyggd **tutorial** som visas vid varje start (klicka eller tryck ENTER för att bläddra, pil upp/ner för att scrolla, `S` för att hoppa över, `TUTORIAL AV` för att stänga av)

## Kom igång

Du behöver Python 3.9 eller nyare (på Windows 3.9–3.13, se nedan) och en terminal som är minst **110 tecken bred och 30 rader hög**
(maximera fönstret om spelet ber dig göra det större).

### Linux

```bash
python3 eldledning.py
```

### macOS

```bash
python3 eldledning.py
```

Standardfönstret i Terminal är litet – dra ut det eller kör i helskärm.

### Windows (PowerShell eller Windows Terminal)

Windows saknar Pythons `curses`-modul, så den installeras med paketet `windows-curses`.
Det paketet finns än så länge bara för **Python 3.9–3.13** – inte för 3.14/3.15. Har du en
nyare Python, installera 3.13 bredvid den (påverkar inte din vanliga Python):

```powershell
winget install Python.Python.3.13
```

Stäng och öppna PowerShell igen, gå sedan **till mappen där du packade upp spelet**
(kommandona nedan fungerar bara där filerna ligger) och kör, ett kommando i taget:

```powershell
cd C:\sokvag\till\eldledning-repo
py -3.13 -m pip install -r requirements.txt
py -3.13 eldledning.py
```

Har du redan Python 3.9–3.13 som standard fungerar `python` i stället för `py -3.13`.

Enklast: dubbelklicka på `start_windows.bat`. Den letar själv upp en fungerande Python,
installerar `windows-curses` vid behov och startar spelet.

Gör fönstret stort (minst 110×30) innan du startar.

## Så spelar du

1. Läs målen överst: skydd, koordinater (O = öst, N = norr), avstånd och azimut.
2. Välj mål, sätt azimut och elevation, välj laddning och granat, och skjut:

   ```
   MAL A AZ 28.3 EL 41.7 LAD 2 APHE ELD
   ```

3. Spejaren rapporterar var granaten landade ("40 M FÖR KORT, 20 M TILL HÖGER").
   Rätta med `EL` (kort/långt) och `AZ` (höger/vänster) – eller skriv `KORR` så räknar spelet om åt dig.
4. Slå ut alla mål innan granaterna tar slut. Träffa aldrig egna trupper (inom 100 m).

### Kommandon

| Kommando | Vad det gör |
|---|---|
| `MAL A` | Välj vilket mål (A–D) du siktar på |
| `AZ 28.3` | Azimut i grader (0 = norr, 90 = öst) – riktning i sidled |
| `EL 41.7` | Elevation 5–85 grader – styr hur långt granaten flyger |
| `LAD 2` | Laddning 1–3; visar vilken elevation valt mål kräver |
| `HE` / `APHE` | Välj granattyp |
| `ELD` | Skjut |
| `KORR` | FDC räknar om AZ och EL från spejarens senaste rapport (kräver spejare) |
| `BUTIK` | Öppna/stäng butiken; `KOP 1` köper vara nummer 1 |
| `SPARA` | Spara direkt (sker även automatiskt) |
| `?` | Visa tutorialen igen (tryck `?` på tom rad; `TUTORIAL` och `HJALP` fungerar också) |
| `TUTORIAL AV` / `TUTORIAL PA` | Stäng av / sätt på att tutorialen visas automatiskt vid start |
| `NOLLSTALL JA` | Radera all sparad progress |
| `Q` | Spara och avsluta |

Flera kommandon går att skriva på samma rad.

### Granater

| Typ | Radie | Oskyddat | Pansar | Bunker | Per uppdrag |
|---|---|---|---|---|---|
| HE | 60 m | 100 % | 25 % | 15 % | 6 (+ fler vid flera mål) |
| APHE | 30 m | 40 % | 100 % | 60 % | 5 (+ fler vid flera mål) |

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
- **`Could not open requirements file`** – du står i fel mapp. Gå först till mappen med spelets filer.
- **Tecken ser konstiga ut** – spelet använder bara ASCII, men prova Windows Terminal i stället för gamla cmd.exe.

## Licens

MIT – se [LICENSE](LICENSE).
