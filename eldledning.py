#!/usr/bin/env python3
"""
ELDLEDNINGSCENTRAL // IRON NEST-stil (WarGames, gront pa svart)

Fungerar pa Linux, macOS och Windows (Windows behover paketet windows-curses
for Python 3.9-3.13; spelet erbjuder att installera det vid forsta start).

Du styr en artilleripjas. Varje uppdrag har ett eller flera mal (A, B, C, D).
Underrattelsetjansten ger exakta koordinater. FDC (eldledningscentralen) raknar
ut AZ, EL och LAD sa att granaten landar EXAKT dar du vill (PUNKT-kommandot),
inklusive vind. Vindmatningen har dock ett matfel - skjut ett inskjutningsskott
och skriv KORR sa raknar FDC ut det verkliga vindfelet.

Granater: HE, APHE, FRAG, HEAT (maste traffa exakt) och LJUS (belyser omradet
och avslojar okanda fiender). Utan spejare syns varken mal eller nedslag pa
kartan - kop en i BUTIKEN. Poang och uppgraderingar sparas automatiskt
(fil: .eldledning_save.json i din hemmapp).

Starta:
  Linux / macOS:   python3 eldledning.py
  Windows:         python eldledning.py
Terminalen ska vara minst 110 tecken bred och 30 rader hog.

Kommandon (flera pa samma rad ar ok):
  MAL B             valj mal (A-F)        TAB / NASTA / FORRA   bladdra mellan mal
  PUNKT A           FDC raknar ut losning for att landa exakt pa mal A
  PUNKT A 30 -10    30 m ost och 10 m soder om mal A  (OST+ NORR+)
  PUNKT 3375 2328   landa pa exakta koordinater (ost norr)
  AZ 28.35  EL 41.72  LAD 2   satt manuellt (decimaler ar ok)
  HE / APHE / FRAG / HEAT / LJUS   valj granat
  ELD               skjut
  KORR              raknar om losningen fran senaste observerade nedslag
  BUTIK  KOP 1      butiken          SPARA   spara nu
  ?                 tutorial (aven HJALP / TUTORIAL)   TUTORIAL AV / PA
  NOLLSTALL JA      radera all progress                Q   spara och avsluta
Exempel:  PUNKT A HE ELD
"""
import json
import math
import os
import random
import subprocess
import sys
import textwrap
import time

try:
    import curses
except ImportError:          # Windows utan windows-curses
    curses = None

G = 9.81
MAP_M = 6000.0
GUN = (300.0, 300.0)
CHARGES = {1: 160.0, 2: 220.0, 3: 280.0}      # utgangshastighet m/s
DRIFT_K = 0.25        # vindens verkan: forskjutning = K * vind * flygtid
WIND_ERR = 1.5        # vindmatningens standardavvikelse (m/s) - okant for spelaren
SPREAD_R = 0.0015     # slumpmassig spridning i langd (andel av avstand)
SPREAD_AZ = 0.03      # slumpmassig spridning i sidled (grader)
SAVE = os.path.join(os.path.expanduser("~"), ".eldledning_save.json")

# radius: traffzon (m).  dmg: skada i % per traff mot oskyddat / pansar / bunker.
# prec: spridningsfaktor (lagre = noggrannare).  safe: sakerhetsavstand till egna (m).
AMMO_TYPES = {
    "HE":   dict(radius=60, stock=6, prec=1.0, safe=100,
                 dmg={"mjuk": 100, "pansar": 25, "bunker": 15},
                 desc="STOR RADIE, BRA MOT OSKYDDAT, SVAG MOT PANSAR/BUNKER"),
    "APHE": dict(radius=30, stock=5, prec=1.0, safe=70,
                 dmg={"mjuk": 40, "pansar": 100, "bunker": 60},
                 desc="PANSARBRYTANDE, BRA MOT PANSAR OCH BUNKER"),
    "FRAG": dict(radius=150, stock=3, prec=1.0, safe=170,
                 dmg={"mjuk": 70, "pansar": 3, "bunker": 1},
                 desc="MYCKET STOR RADIE, NASTAN INGEN SKADA MOT PANSAR/BUNKER"),
    "HEAT": dict(radius=10, stock=2, prec=0.4, safe=25,
                 dmg={"mjuk": 100, "pansar": 100, "bunker": 100},
                 desc="MASTE TRAFFA EXAKT (10 M). SLAR UT VAD SOM HELST I ETT SKOTT"),
    "LJUS": dict(radius=700, stock=3, prec=1.0, safe=0, light=True,
                 dmg={"mjuk": 0, "pansar": 0, "bunker": 0},
                 desc="BELYSER OMRADET (700 M) OCH AVSLOJAR FIENDER. INGEN SKADA"),
}
# profilnyckel och maxniva for extra granater i butiken
EXTRA = {"HE": ("he_extra", 4), "APHE": ("aphe_extra", 3), "FRAG": ("frag_extra", 3),
         "HEAT": ("heat_extra", 2), "LJUS": ("ljus_extra", 3)}

SKYDD = {"mjuk": "OSKYDDAT", "pansar": "PANSRAT", "bunker": "BETONGBUNKER"}
SKYDD_KORT = {"mjuk": "OSKYDD", "pansar": "PANSAR", "bunker": "BUNKER"}

TYPES = [
    ("INFANTERI", "mjuk"),
    ("LASTBILSKOLONN", "mjuk"),
    ("PANSARVAGN", "pansar"),
    ("BUNKER", "bunker"),
    ("RADARSTATION", "mjuk"),
    ("ARTILLERIBATTERI", "mjuk"),
    ("PANSARPLUTON", "pansar"),
    ("KOMMANDOBUNKER", "bunker"),
]
LETTERS = "ABCDEF"

# Butiken: (namn, pris). Ordningen = KOP-numret. Spara numreringen!
SHOP = [
    ("SPEJARE (DETTA UPPDRAG)", 150),
    ("FAST SPEJARE (ALLA UPPDRAG)", 1200),
    ("EXTRA HE +1 PER UPPDRAG", 250),
    ("EXTRA APHE +1 PER UPPDRAG", 300),
    ("PRECISIONSOPTIK -15% SPRIDNING", 400),
    ("FORTROENDE +1", 500),
    ("EXTRA FRAG +1 PER UPPDRAG", 250),
    ("EXTRA HEAT +1 PER UPPDRAG", 600),
    ("EXTRA LJUS +1 PER UPPDRAG", 150),
]
SHOP_AMMO = {2: "HE", 3: "APHE", 6: "FRAG", 7: "HEAT", 8: "LJUS"}

# Tutorial: lista av (rubrik, rader). En rad ar text eller (kommando, forklaring).
TUTORIAL = [
    ("SPELIDEEN", [
        "Du styr en artilleripjas (G pa kartan). Varje uppdrag har ett eller flera mal, A till D.",
        "Underrattelsetjansten ger EXAKTA koordinater, avstand och azimut samt hur skyddat "
        "varje mal ar.",
        "Du behover inte rakna sjalv: skriv PUNKT A sa raknar FDC ut AZ, EL och LAD sa att "
        "granaten landar exakt pa mal A - inklusive vind.",
        "Haken: vindmatningen har ett okant matfel, och varje skott har en liten slumpmassig "
        "spridning. Skjut ett inskjutningsskott, las av var det landade och skriv KORR - "
        "da raknar FDC ut det verkliga vindfelet och nasta skott blir mycket exakt.",
        "Sla ut ALLA mal innan granaterna tar slut - utan att traffa egna trupper (#).",
        "Misslyckas du eller traffar egna trupper tappar du fortroende. Nar det ar slut "
        "borjar en ny omgang (poang och uppgraderingar behalls).",
        "Utan spejare syns varken mal eller nedslag pa kartan och du far inga "
        "nedslagsrapporter. Kop en spejare i BUTIKEN - eller anvand LJUS.",
    ]),
    ("SIKTA OCH SKJUTA", [
        ("MAL A", "Valj mal (A-F). Pilen > i listan visar valt mal."),
        ("TAB / NASTA", "Bladdra till nasta mal. SHIFT+TAB / FORRA = foregaende. "
                        "Pil hoger/vanster gor samma sak pa tom kommandorad."),
        ("PUNKT A", "FDC raknar ut AZ, EL och LAD sa granaten landar EXAKT pa mal A "
                    "(vind inraknad). Utan namn: valt mal."),
        ("PUNKT A 30 -10", "Samma, men 30 m ost och 10 m soder om mal A (ost +, norr +)."),
        ("PUNKT 3375 2328", "Landa pa exakta koordinater (ost norr, i meter)."),
        ("AZ 28.35", "Azimut manuellt: riktning i sidled, 0 = norr, 90 = ost. Decimaler ok."),
        ("EL 41.72", "Elevation manuellt, 5-85 grader: styr hur LANGT granaten flyger."),
        ("LAD 2", "Laddning 1-3 (mer kraft = lagre vinkel). PUNKT valjer sjalv om du inte har valt."),
        ("ELD", "Skjut. Kraver AZ, EL, LAD och vald granat."),
        ("KORR", "Raknar om losningen fran senaste OBSERVERADE nedslag (spejare eller LJUS): "
                 "FDC hittar vindfelet. Galler hela uppdraget - gor det innan du byter mal."),
    ]),
    ("GRANATER", [
        ("HE", "Sprangranat. Radie 60 m. Bra mot oskyddat, svag mot pansar (25%) och bunker (15%)."),
        ("APHE", "Pansarbrytande. Radie 30 m. 100% mot pansar, 60% mot bunker, 40% mot oskyddat."),
        ("FRAG", "Splitter. MYCKET stor radie (150 m) men nastan ingen skada mot pansar (3%) "
                 "och bunker (1%). 70% mot oskyddat - bra mot kluster. Hall 170 m till egna."),
        ("HEAT", "Hogexplosivt pansarbrytande. Maste traffa EXAKT (inom 10 m), men slar ut "
                 "VAD SOM HELST i ett skott. Mycket liten spridning. Fa granater per uppdrag."),
        ("LJUS", "Belysningsgranat. Ingen skada. Belyser 700 m runt nedslaget pa kartan och "
                 "avslojar fiender i narheten - ocksa okanda kontakter som inte finns i "
                 "listan (bonusmal markerade med *). Nedslaget syns, sa du kan KORR:a pa det."),
        "Skadetabellen och antal kvar visas till hoger pa skarmen.",
    ]),
    ("OVRIGA KOMMANDON", [
        ("BUTIK", "Oppna/stang butiken. KOP 1 kopar vara nummer 1 (kraver poang)."),
        ("SPARA", "Spara direkt. Spelet sparar ocksa automatiskt efter varje uppdrag och kop."),
        ("?", "Visa den har tutorialen igen (tryck ? pa tom rad, eller skriv HJALP)."),
        ("TUTORIAL AV / PA", "Stang av / satt pa att tutorialen visas automatiskt vid start."),
        ("NOLLSTALL JA", "Radera ALL sparad progress."),
        ("Q", "Spara och avsluta."),
        "Flera kommandon pa en rad fungerar, t.ex.  PUNKT A HEAT ELD",
    ]),
    ("SKARMEN", [
        "Overst: listan med mal (skydd, koordinater O=ost N=norr, avstand, azimut, styrka %), "
        "exakt information om valt mal, vind, egna trupper, dina installningar och "
        "BERAKNAT NEDSLAG - var FDC tror att granaten landar, med flygtid och spridning (1 sigma).",
        "Mitten: kartan. G = din pjas, A-F = mal, x = utslaget mal, # = egna trupper, "
        ". = belyst omrade, siffror = dina nedslag. Mal, # och nedslag syns bara med spejare "
        "(eller om de belysts av LJUS).",
        "Hoger: skjuttabell (elevation utan vind) och granattabell (kvar, radie, skada i %).",
        "Langst ner: de senaste meddelandena och kommandoraden KOMMANDO>.",
        "Vinden anges som FRAN en riktning. Matfelet (+/-) betyder att den verkliga vinden "
        "avviker - det ar det KORR hittar.",
        "Egna trupper (#) far aldrig traffas: sakerhetsavstandet ar olika per granat "
        "(visas pa skarmen).",
    ]),
    ("TIPS: SA TRAFFAR DU EXAKT", [
        "1. TAB bland malen och lasa informationen. Valj ett mal.",
        "2. PUNKT A - FDC satter AZ, EL och LAD. Kolla BERAKNAT NEDSLAG.",
        "3. Skjut ett inskjutningsskott: HE (eller LJUS om du saknar spejare), ELD.",
        "4. Las rapporten. Skriv KORR - FDC raknar ut vindfelet och rattar losningen.",
        "5. Valj ratt granat: HEAT pa pansar och bunkrar, HE/FRAG pa oskyddat, APHE som mellanting.",
        "6. ELD igen. Vindkorrigeringen galler aven nasta mal - du behover bara gora den en gang.",
        "Skjut LJUS mot omraden dar du tror att det finns mer - bonusmal ger extra poang.",
        "Tryck ? nar som helst for att se den har tutorialen igen.",
        "Tryck ENTER eller klicka for att borja. Lycka till!",
    ]),
]

MIN_W, MIN_H = 110, 30

DEFAULT_PROFILE = dict(points=0, run_done=0, trust=3, best=0, won=0,
                       he_extra=0, aphe_extra=0, frag_extra=0, heat_extra=0,
                       ljus_extra=0, optics=0, perm_spotter=False,
                       tutorial_done=False, tutorial_auto=True)


def enter_keys():
    return (10, 13, curses.KEY_ENTER, getattr(curses, "PADENTER", 459))


def num(tok):
    """Tolkar ett tal; None om det inte ar ett andligt tal."""
    try:
        v = float(tok)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


# ---------- sparning ----------
def load_profile():
    p = dict(DEFAULT_PROFILE)
    try:
        with open(SAVE, encoding="utf-8") as f:
            d = json.load(f)
        for k, v in DEFAULT_PROFILE.items():
            if k in d and isinstance(d[k], bool) == isinstance(v, bool) \
                    and isinstance(d[k], (int, bool)):
                p[k] = d[k]
    except (OSError, ValueError, TypeError):
        pass
    p["points"] = max(0, int(p["points"]))
    p["run_done"] = max(0, int(p["run_done"]))
    p["trust"] = min(5, max(1, int(p["trust"])))
    for key, mx in EXTRA.values():
        p[key] = min(mx, max(0, int(p[key])))
    p["optics"] = min(3, max(0, int(p["optics"])))
    p["perm_spotter"] = bool(p["perm_spotter"])
    p["tutorial_done"] = bool(p["tutorial_done"])
    p["tutorial_auto"] = bool(p["tutorial_auto"])
    return p


def save_profile(p):
    try:
        tmp = SAVE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(p, f)
        os.replace(tmp, SAVE)
        return True
    except OSError:
        return False


# ---------- ballistik ----------
def rng_for(v, e):
    return v * v * math.sin(2 * math.radians(e)) / G


def elev_for(v, r):
    if r <= 0:
        return None
    s = r * G / (v * v)
    if s > 1:
        return None
    return math.degrees(0.5 * math.asin(s))


def tof(v, e):
    return 2 * v * math.sin(math.radians(e)) / G


def predict(az, el, v, wvec):
    """Var landar granaten (utan slumpspridning) med vinden wvec? -> (x, y, flygtid)"""
    R = rng_for(v, el)
    T = tof(v, el)
    a = math.radians(az)
    return (GUN[0] + R * math.sin(a) + DRIFT_K * wvec[0] * T,
            GUN[1] + R * math.cos(a) + DRIFT_K * wvec[1] * T, T)


def solve_shot(px, py, v, wvec):
    """Raknar ut (az, el, flygtid, vinddrift) sa att granaten landar pa (px, py).
    None om punkten inte nas med hastigheten v."""
    dx, dy = px - GUN[0], py - GUN[1]
    wox = woy = 0.0
    for _ in range(80):
        ex, ey = dx - wox, dy - woy
        el = elev_for(v, math.hypot(ex, ey))
        if el is None:
            return None
        T = tof(v, el)
        nx, ny = DRIFT_K * wvec[0] * T, DRIFT_K * wvec[1] * T
        done = abs(nx - wox) + abs(ny - woy) < 1e-7
        wox, woy = nx, ny
        if done:
            break
    ex, ey = dx - wox, dy - woy
    el = elev_for(v, math.hypot(ex, ey))
    if el is None:
        return None
    az = math.degrees(math.atan2(ex, ey)) % 360
    return az, el, tof(v, el), (wox, woy)


def compass(dx, dy):
    ang = math.degrees(math.atan2(dx, dy)) % 360
    return ["N", "NO", "O", "SO", "S", "SV", "V", "NV"][int((ang + 22.5) // 45) % 8]


def offset_text(ix, iy, ax, ay):
    """Avvikelse fran (ax, ay) sett fran pjasen: langd (for kort/langt) och sida."""
    d = math.hypot(ax - GUN[0], ay - GUN[1]) or 1.0
    ux, uy = (ax - GUN[0]) / d, (ay - GUN[1]) / d
    dx, dy = ix - ax, iy - ay
    along = dx * ux + dy * uy
    cross = dx * uy - dy * ux              # positivt = till hoger
    parts = []
    if abs(along) >= 0.05:
        parts.append(f"{abs(along):.1f} M {'FOR LANGT' if along > 0 else 'FOR KORT'}")
    if abs(cross) >= 0.05:
        parts.append(f"{abs(cross):.1f} M TILL {'HOGER' if cross > 0 else 'VANSTER'}")
    return ", ".join(parts) or "PRECIS PA PUNKTEN"


# ---------- uppdrag ----------
class Target:
    def __init__(self, letter, name, hard, x, y, hidden=False, bonus=False):
        self.letter = letter
        self.name = name
        self.hard = hard
        self.x = x
        self.y = y
        self.hp = 100
        self.hidden = hidden      # okand kontakt: syns inte i listan forran den belysts
        self.bonus = bonus        # valfritt mal: behovs inte for att klara uppdraget
        self.seen = False         # belyst av LJUS: syns pa kartan aven utan spejare
        dx, dy = x - GUN[0], y - GUN[1]
        self.dist = math.hypot(dx, dy)
        self.bearing = math.degrees(math.atan2(dx, dy)) % 360

    @property
    def alive(self):
        return self.hp > 0


def place_targets(count):
    """Slumpar positioner. Ibland ligger mal tatt ihop sa en granat kan traffa flera."""
    def inside(x, y):
        if not (200 <= x <= 5800 and 200 <= y <= 5800):
            return False
        return 1400 <= math.hypot(x - GUN[0], y - GUN[1]) <= 5300

    pts = []
    tries = 0
    while len(pts) < count and tries < 500:
        tries += 1
        if pts and random.random() < 0.35:
            bx, by = random.choice(pts)
            a = random.uniform(0, 2 * math.pi)
            d = random.uniform(110, 260)
            x, y = bx + d * math.sin(a), by + d * math.cos(a)
            if not inside(x, y):
                continue
            if any(math.hypot(x - px, y - py) < 100 for px, py in pts):
                continue
        else:
            b = math.radians(random.uniform(8, 82))
            d = random.uniform(1500, 5200)
            x, y = GUN[0] + d * math.sin(b), GUN[1] + d * math.cos(b)
            if any(math.hypot(x - px, y - py) < 500 for px, py in pts):
                continue
        pts.append((x, y))
    return pts


class Mission:
    def __init__(self, n, prof):
        self.n = n
        count = min(4, 1 + n // 2)
        pool = TYPES[:min(len(TYPES), 3 + n // 2)]
        self.targets = []
        for i, (x, y) in enumerate(place_targets(count)):
            name, hard = random.choice(pool)
            self.targets.append(Target(LETTERS[i], name, hard, x, y))
        nmain = len(self.targets)
        self.stock = {}
        for name, spec in AMMO_TYPES.items():
            base = spec["stock"] + prof[EXTRA[name][0]]
            if name in ("HE", "APHE"):
                base += 2 * (nmain - 1)
            elif name in ("FRAG", "LJUS"):
                base += nmain - 1
            self.stock[name] = base
        self.wind = random.randint(0, min(10, 2 + n))
        self.wfrom = random.randint(0, 359)
        # verkligt vindfel (okant for spelaren): matningen stammer inte exakt
        self.werr = (max(-3.0, min(3.0, random.gauss(0, WIND_ERR))),
                     max(-3.0, min(3.0, random.gauss(0, WIND_ERR))))
        self.friend = None
        self.friend_seen = False
        if n >= 3 and random.random() < 0.5:
            for _ in range(40):
                anchor = random.choice(self.targets)
                a = random.uniform(0, 2 * math.pi)
                d = random.uniform(170, 260)
                fx = min(5850, max(150, anchor.x + d * math.sin(a)))
                fy = min(5850, max(150, anchor.y + d * math.cos(a)))
                if all(math.hypot(fx - t.x, fy - t.y) >= 150 for t in self.targets):
                    self.friend = (fx, fy)
                    break
        # okanda kontakter (bonusmal) - syns forst nar de belysts av LJUS
        if n >= 2 and random.random() < 0.65:
            nh = 1 if n < 4 else random.choice([1, 2])
            for _ in range(nh):
                for _try in range(60):
                    anchor = random.choice(self.targets[:nmain])
                    a = random.uniform(0, 2 * math.pi)
                    d = random.uniform(150, 450)
                    x, y = anchor.x + d * math.sin(a), anchor.y + d * math.cos(a)
                    if not (200 <= x <= 5800 and 200 <= y <= 5800):
                        continue
                    if math.hypot(x - GUN[0], y - GUN[1]) < 1000:
                        continue
                    if any(math.hypot(x - t.x, y - t.y) < 100 for t in self.targets):
                        continue
                    if self.friend and math.hypot(x - self.friend[0], y - self.friend[1]) < 120:
                        continue
                    name, hard = random.choice(pool)
                    self.targets.append(Target(LETTERS[len(self.targets)], name, hard,
                                               x, y, hidden=True, bonus=True))
                    break
        self.impacts = []      # (x, y, syns_pa_kartan)
        self.lit = []          # (x, y, radie)

    def main_targets(self):
        return [t for t in self.targets if not t.bonus]

    def dmg_ammo(self):
        return sum(v for k, v in self.stock.items() if not AMMO_TYPES[k].get("light"))

    def wind_vec(self):
        th = math.radians(self.wfrom + 180)      # vinden blaser TILL
        return self.wind * math.sin(th), self.wind * math.cos(th)

    def true_wind_vec(self):
        wx, wy = self.wind_vec()
        return wx + self.werr[0], wy + self.werr[1]


# ---------- spel ----------
class Game:
    def __init__(self):
        self.p = load_profile()
        self.log = []
        self.buf = ""
        self.shop_open = False
        self.gameover = False
        self.tut = 0 if self.p["tutorial_auto"] else None   # visas vid varje start
        self.tut_scroll = 0
        self._click_t = 0.0
        self.say("HEJ. SKA VI SPELA ETT SPEL?", "hi")
        if self.p["run_done"] or self.p["points"] or self.p["won"]:
            self.say(f"SPARAD PROGRESS LADDAD. POANG {self.p['points']}, "
                     f"UPPDRAG KLARADE {self.p['won']}.", "n")
        self.say("ELDLEDNINGSCENTRAL ANSLUTEN.", "n")
        self.new_mission()

    # smarta egenskaper for sparade varden
    @property
    def trust(self):
        return self.p["trust"]

    @trust.setter
    def trust(self, v):
        self.p["trust"] = v

    @property
    def points(self):
        return self.p["points"]

    @points.setter
    def points(self, v):
        self.p["points"] = max(0, int(v))

    @property
    def cur(self):
        return self.m.targets[self.sel]

    def save(self):
        return save_profile(self.p)

    def say(self, text, kind="n"):
        for ln in textwrap.wrap(text, 78) or [""]:
            self.log.append((ln, kind))
        del self.log[:-200]

    def vis(self):
        """Index for mal som syns i listan och lever."""
        return [i for i, t in enumerate(self.m.targets) if not t.hidden and t.alive]

    def wvec_eff(self):
        wx, wy = self.m.wind_vec()
        return wx + self.wcorr[0], wy + self.wcorr[1]

    def new_mission(self):
        self.mn = self.p["run_done"] + 1
        self.m = Mission(self.mn, self.p)
        self.sel = 0
        self.az = None
        self.elev = None
        self.charge = None
        self.charge_auto = False   # True = FDC valde laddningen (valjs om vid nasta PUNKT)
        self.ammo_type = None
        self.aim = None            # punkt som valts med PUNKT (utan korrektion)
        self.wcorr = (0.0, 0.0)    # FDC:s uppskattade vindfel (m/s), fran KORR
        self.wsamples = []         # alla vindfelsuppskattningar (medelvarde = wcorr)
        self.shot_type = None
        self.shot_target = 0
        self.shot_aim = None
        self.shot_pred = None
        self.shot_T = 30.0
        self.last_err = None       # senaste observerade nedslag minus FDC:s forutsagelse
        self.last_T = None
        self.last_aim_pt = None
        self.state = "aim"
        self.endmsg = ""
        self.gameover = False
        self.shop_open = False
        free = self.mn == 1
        self.spotter = self.p["perm_spotter"] or free
        m = self.m
        nt = len(m.main_targets())
        self.say(f"--- UPPDRAG {self.mn}: {nt} MAL ---", "hi")
        who = "SPEJARE" if self.spotter else "UNDERRATTELSE"
        if nt == 1:
            self.say(f"{who}: ELDUPPDRAG! {m.targets[0].name}, "
                     f"{SKYDD[m.targets[0].hard]}. SE LISTAN OVAN.", "fo")
        else:
            self.say(f"{who}: ELDUPPDRAG! {nt} MAL (A-{LETTERS[nt - 1]}), SE LISTAN OVAN. "
                     f"TAB BLADDRAR MELLAN MAL. ALLA MASTE SLAS UT.", "fo")
        if self.mn >= 2:
            self.say("OBS: OKANDA KONTAKTER KAN FINNAS I NARHETEN. LJUS AVSLOJAR DEM.", "n")
        self.say(f"VIND {m.wind} M/S FRAN {m.wfrom:03d} GRADER (MATNING +/-{WIND_ERR:.1f} M/S). "
                 f"GRANATER: {self.stock_text()}.", "fo")
        if m.friend:
            safe = " ".join(f"{k} {v['safe']}" for k, v in AMMO_TYPES.items() if v["safe"])
            self.say(f"VARNING: EGNA TRUPPER VID OST {m.friend[0]:.1f} NORR {m.friend[1]:.1f}. "
                     f"SAKERHETSAVSTAND (M): {safe}.", "bad")
        if self.spotter:
            if free and not self.p["perm_spotter"]:
                self.say("SPEJARE PA PLATS (GRATIS UPPDRAG 1).", "ok")
            self.report = "INGEN ANNU"
        else:
            self.say("INGEN SPEJARE PA PLATS: MAL OCH NEDSLAG SYNS EJ PA KARTAN. "
                     "KOP EN I BUTIKEN ELLER ANVAND LJUS.", "bad")
            self.report = "INGEN SPEJARE - NEDSLAG OBSERVERAS EJ"
        self.say_fdc()
        self.say("SKRIV PUNKT FOR ATT FA EN LOSNING. VALJ GRANAT. ? = HJALP.", "hi")

    def say_fdc(self):
        t = self.cur
        self.say(f"FDC: MAL {t.letter} ({t.name}): O {t.x:.1f}  N {t.y:.1f}  "
                 f"AVSTAND {t.dist:.1f} M  AZIMUT {t.bearing:.3f}", "hi")

    def stock_text(self):
        return "  ".join(f"{k} {v}" for k, v in self.m.stock.items())

    # ----- tutorial -----
    def open_tutorial(self):
        self.tut = 0
        self.tut_scroll = 0

    def close_tutorial(self):
        self.tut = None
        if not self.p["tutorial_done"]:
            self.p["tutorial_done"] = True
            self.save()

    def tut_next(self):
        if self.tut is None:
            return
        if self.tut + 1 >= len(TUTORIAL):
            self.close_tutorial()
        else:
            self.tut += 1
            self.tut_scroll = 0

    def tut_key(self, k):
        if k in enter_keys() or k in (32, curses.KEY_RIGHT):
            self.tut_next()
        elif k == curses.KEY_DOWN:
            self.tut_scroll += 1                 # begransas i draw_tutorial
        elif k == curses.KEY_UP:
            self.tut_scroll = max(0, self.tut_scroll - 1)
        elif k in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, 8):
            self.tut = max(0, self.tut - 1)
            self.tut_scroll = 0
        elif k in (27, ord("s"), ord("S"), ord("q"), ord("Q")):
            self.close_tutorial()

    def click(self):
        now = time.monotonic()
        if self.tut is None or now - self._click_t < 0.3:
            return
        self._click_t = now
        self.tut_next()

    # ----- butik -----
    def shop_status(self, i):
        p = self.p
        if i == 0:
            if self.spotter:
                return "KLAR", False
            if self.state != "aim":
                return "I UPPDRAG", False
            return "", True
        if i == 1:
            return ("AGS", False) if p["perm_spotter"] else ("", True)
        if i in SHOP_AMMO:
            key, mx = EXTRA[SHOP_AMMO[i]]
            return f"{p[key]}/{mx}", p[key] < mx
        if i == 4:
            return f"{p['optics']}/3", p["optics"] < 3
        if i == 5:
            return f"{p['trust']}/5", p["trust"] < 5
        return "", False

    def buy(self, n):
        if not 1 <= n <= len(SHOP):
            self.say(f"FINNS INGEN VARA {n}.", "bad")
            return
        i = n - 1
        label, price = SHOP[i]
        txt, ok = self.shop_status(i)
        if not ok:
            self.say(f"KAN INTE KOPA {label}: {txt}", "bad")
            return
        if self.points < price:
            self.say(f"FOR FA POANG ({self.points}/{price}).", "bad")
            return
        self.points -= price
        p = self.p
        live = self.state == "aim"
        if i == 0:
            self.spotter = True
            self.report = "SPEJARE PA PLATS"
        elif i == 1:
            p["perm_spotter"] = True
            if live:
                self.spotter = True
                self.report = "SPEJARE PA PLATS"
        elif i in SHOP_AMMO:
            name = SHOP_AMMO[i]
            p[EXTRA[name][0]] += 1
            if live:
                self.m.stock[name] += 1
        elif i == 4:
            p["optics"] += 1
        elif i == 5:
            p["trust"] += 1
        self.say(f"KOPT: {label} (-{price} POANG). KVAR {self.points}.", "ok")
        self.save()

    # ----- inmatning -----
    def key(self, k):
        if self.tut is not None:
            self.tut_key(k)
            return False
        back_keys = (127, 8, curses.KEY_BACKSPACE)
        if k == ord("?") and not self.buf and self.state != "flight":
            self.open_tutorial()          # ? pa tom rad oppnar tutorialen direkt
            return False
        if self.state == "aim":
            if k == 9:
                self.step_target(1)
                return False
            if k == getattr(curses, "KEY_BTAB", 353):
                self.step_target(-1)
                return False
            if not self.buf and k == curses.KEY_RIGHT:
                self.step_target(1)
                return False
            if not self.buf and k == curses.KEY_LEFT:
                self.step_target(-1)
                return False
        if k in enter_keys():
            line = self.buf.strip()
            self.buf = ""
            return self.enter(line)
        if k in back_keys:
            self.buf = self.buf[:-1]
        elif 32 <= k < 127 and len(self.buf) < 60:
            self.buf += chr(k)
        return False

    def enter(self, line):
        if self.state == "flight":
            return False
        if self.state == "end":
            u = line.upper().split()
            if u and u[0] in ("Q", "SLUT", "EXIT"):
                return True
            if u and u[0] in ("BUTIK", "KOP", "KOPA", "SPARA", "HJALP",
                              "TUTORIAL", "INTRO", "NOLLSTALL", "?", "H"):
                self.say("> " + line.upper(), "n")
                return self.run(line)
            self.new_mission()
            return False
        if not line:
            return False
        self.say("> " + line.upper(), "n")
        return self.run(line)

    def set_ammo(self, name):
        self.ammo_type = name
        spec = AMMO_TYPES[name]
        self.say(f"GRANAT: {name}. RADIE {spec['radius']} M. {spec['desc']}. "
                 f"{self.m.stock[name]} KVAR.", "hi")

    def select_target(self, tok):
        idx = None
        if len(tok) == 1 and tok in LETTERS:
            idx = LETTERS.index(tok)
        elif tok.isdigit() and 1 <= int(tok) <= len(self.m.targets):
            idx = int(tok) - 1
        if idx is None or idx >= len(self.m.targets) or self.m.targets[idx].hidden:
            letters = "".join(self.m.targets[i].letter for i in range(len(self.m.targets))
                              if not self.m.targets[i].hidden)
            self.say(f"OGILTIGT MAL. VALJ NAGON AV: {', '.join(letters)}.", "bad")
            return False
        if not self.m.targets[idx].alive:
            self.say(f"MAL {LETTERS[idx]} AR REDAN UTSLAGET.", "bad")
            return False
        if idx != self.sel:
            self.sel = idx
            self.aim = None
            self.last_err = None
        self.say_fdc()
        return True

    def step_target(self, d):
        vis = self.vis()
        if not vis:
            return
        if len(vis) == 1:
            self.say(f"BARA ETT MAL KVAR: {self.m.targets[vis[0]].letter}.", "n")
            self.sel = vis[0]
            return
        pos = vis.index(self.sel) if self.sel in vis else 0
        self.sel = vis[(pos + d) % len(vis)]
        self.aim = None
        self.last_err = None
        self.say_fdc()

    def reselect(self):
        if self.cur.alive and not self.cur.hidden:
            return
        vis = self.vis()
        if vis:
            self.sel = vis[0]
            self.aim = None
            self.last_err = None

    # ----- eldledning -----
    def set_solution(self, ax, ay, label):
        """FDC raknar ut AZ/EL/LAD for att landa pa (ax, ay). True om det lyckades."""
        if not (0 <= ax <= MAP_M and 0 <= ay <= MAP_M):
            self.say(f"PUNKTEN O{ax:.1f} N{ay:.1f} LIGGER UTANFOR KARTAN (0-{MAP_M:.0f}).", "bad")
            return False
        wv = self.wvec_eff()
        manual = bool(self.charge) and not self.charge_auto
        order = [self.charge] if manual else [1, 2, 3]
        chosen = None
        why = ""
        for c in order:
            sol = solve_shot(ax, ay, CHARGES[c], wv)
            if sol is None:
                why = (f"LADDNING {c} NAR INTE (MAX {rng_for(CHARGES[c], 45):.0f} M). "
                       "VALJ HOGRE LADDNING.")
            elif sol[1] < 5.0:
                why = f"FOR NARA FOR LADDNING {c} (EL {sol[1]:.1f} < 5). VALJ LAGRE LADDNING."
            else:
                chosen = (c, sol)
                break
        if chosen is None:
            self.say("FDC: INGEN LOSNING. " + why, "bad")
            return False
        c, (az, el, T, drift) = chosen
        self.charge = c
        self.charge_auto = not manual
        self.az = round(az, 2)
        self.elev = round(el, 2)
        self.aim = (ax, ay)
        self.say(f"FDC: LOSNING MOT {label} O{ax:.1f} N{ay:.1f}: AZ {self.az:.2f}  "
                 f"EL {self.elev:.2f}  LAD {c}.", "hi")
        self.say(f"  FLYGTID {T:.1f} S. VINDDRIFT O{drift[0]:+.1f} N{drift[1]:+.1f} M "
                 f"(INRAKNAD). SKRIV ELD.", "n")
        return True

    def korr(self):
        if self.state != "aim":
            self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
            return
        if self.last_err is None or self.charge is None:
            self.say("FDC: INGEN OBSERVERAD NEDSLAGSRAPPORT ATT KORRIGERA MOT. "
                     "(KRAVER SPEJARE ELLER LJUS.)", "bad")
            return
        ex, ey = self.last_err
        T = max(1.0, self.last_T or 1.0)
        # absolut uppskattning av vindfelet fran detta nedslag; fler matningar -> medelvarde
        sample = (self.wcorr[0] + ex / (DRIFT_K * T), self.wcorr[1] + ey / (DRIFT_K * T))
        self.wsamples.append(sample)
        use = self.wsamples[-4:]
        wc = (sum(s[0] for s in use) / len(use), sum(s[1] for s in use) / len(use))
        mag = math.hypot(*wc)
        if mag > 6.0:
            wc = (wc[0] * 6.0 / mag, wc[1] * 6.0 / mag)
        self.wcorr = wc
        self.last_err = None
        pt = self.aim or self.last_aim_pt
        self.say(f"FDC: VINDFEL UPPSKATTAT TILL O{wc[0]:+.2f} N{wc[1]:+.2f} M/S "
                 f"(MEDEL AV {len(use)} NEDSLAG; FLER NEDSLAG = SAKRARE).", "hi")
        if pt is not None:
            self.set_solution(pt[0], pt[1], "KORRIGERAD")

    def fire(self):
        if self.state != "aim":
            self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
            return
        if None in (self.az, self.elev, self.charge):
            self.say("FDC: SATT AZ, EL OCH LAD (ELLER SKRIV PUNKT) INNAN ELD.", "bad")
            return
        m = self.m
        if self.ammo_type is None:
            self.say("FDC: VALJ GRANAT (HE, APHE, FRAG, HEAT ELLER LJUS) INNAN ELD.", "bad")
            return
        if m.stock[self.ammo_type] <= 0:
            self.say(f"SLUT PA {self.ammo_type}. VALJ ANNAN GRANAT.", "bad")
            return
        spec = AMMO_TYPES[self.ammo_type]
        v = CHARGES[self.charge]
        R = rng_for(v, self.elev)
        T = tof(v, self.elev)
        m.stock[self.ammo_type] -= 1
        self.shot_type = self.ammo_type
        self.shot_target = self.sel
        self.shot_aim = self.aim
        mult = (0.85 ** self.p["optics"]) * spec["prec"]
        Ra = R * (1 + random.gauss(0, SPREAD_R * mult))
        aza = math.radians(self.az + random.gauss(0, SPREAD_AZ * mult))
        wx, wy = m.true_wind_vec()
        self.pending = (GUN[0] + Ra * math.sin(aza) + DRIFT_K * wx * T,
                        GUN[1] + Ra * math.cos(aza) + DRIFT_K * wy * T)
        px, py, _ = predict(self.az, self.elev, v, self.wvec_eff())
        self.shot_pred = (px, py)
        self.shot_T = T
        self.t_left = T
        self.shop_open = False
        self.state = "flight"
        self.say(f"ELD! {self.shot_type} MOT MAL {self.cur.letter}: LAD {self.charge} "
                 f"AZ {self.az:.2f} EL {self.elev:.2f} - NEDSLAG OM {T:.1f} S", "hi")

    def update(self, dt):
        if self.state == "flight":
            self.t_left -= dt * 8.0           # tidsforskjutning
            if self.t_left <= 0:
                self.impact()

    def impact(self):
        m = self.m
        typ = self.shot_type
        spec = AMMO_TYPES[typ]
        light = spec.get("light", False)
        ix, iy = self.pending
        st = m.targets[self.shot_target]
        aim = self.shot_aim or (st.x, st.y)
        self.last_aim_pt = aim
        m.impacts.append((ix, iy, self.spotter or light))
        n = len(m.impacts)
        off = offset_text(ix, iy, aim[0], aim[1])
        where = "SIKTPUNKT" if self.shot_aim else f"MAL {st.letter}"
        observed = self.spotter or light
        if observed and self.shot_pred is not None:
            self.last_err = (ix - self.shot_pred[0], iy - self.shot_pred[1])
            self.last_T = self.shot_T
        else:
            self.last_err = None

        # egna trupper
        if (not light and m.friend and spec["safe"] > 0
                and math.hypot(ix - m.friend[0], iy - m.friend[1]) <= spec["safe"]):
            self.say("NEDSLAG! EGNA TRUPPER RAPPORTERAR ATT DE BLIVIT TRAFFADE!", "bad")
            self.report = "EGNA TRUPPER TRAFFADE!"
            self.trust -= 1
            self.points -= 100
            self.end_mission("EGNA TRUPPER TRAFFADES. UPPDRAGET AVBRUTET.", False)
            return

        if light:
            self.light_impact(ix, iy, spec["radius"], n, off, where)
        else:
            self.damage_impact(ix, iy, spec, typ, n, off, where, observed)

        if all(not t.alive for t in m.main_targets()):
            bonus = 50 + 40 * m.dmg_ammo()
            self.points += bonus
            self.p["won"] += 1
            self.say(f"ALLA MAL UTSLAGNA! BONUS +{bonus} POANG", "ok")
            self.end_mission("UPPDRAGET LYCKADES.", True)
        elif m.dmg_ammo() <= 0:
            left = sum(1 for t in m.main_targets() if t.alive)
            self.say(f"SLUT PA GRANATER. {left} MAL OVERLEVDE.", "bad")
            self.trust -= 1
            self.end_mission("UPPDRAGET MISSLYCKADES.", False)
        else:
            self.say(f"GRANATER KVAR: {self.stock_text()}", "n")
            self.state = "aim"

    def damage_impact(self, ix, iy, spec, typ, n, off, where, observed):
        m = self.m
        hits, destroyed = [], []
        for t in m.targets:
            if t.alive and math.hypot(ix - t.x, iy - t.y) <= spec["radius"]:
                dmg = spec["dmg"][t.hard]
                hid = t.hidden
                t.hp -= dmg
                hits.append((t, dmg, hid))
                if t.hp <= 0:
                    t.hp = 0
                    destroyed.append((t, hid))
        if self.spotter:
            self.report = f"NEDSLAG {n} ({typ}) O{ix:.1f} N{iy:.1f}: {off}"
            self.say(f"SPEJARE: NEDSLAG O{ix:.1f} N{iy:.1f}. {off} ({where}).", "fo")
            seen_hits = [(t, d) for t, d, hid in hits if not hid and t.alive]
            if seen_hits:
                self.say("  TRAFF: " + ", ".join(f"MAL {t.letter} -{d}% ({t.hp}% KVAR)"
                                                 for t, d in seen_hits), "ok")
        else:
            self.report = f"NEDSLAG {n} ({typ}) EJ OBSERVERAT"
            self.say("NEDSLAG EJ OBSERVERAT - INGEN SPEJARE.", "n")
        who = "SPEJARE" if self.spotter else "SIGNALSPANING"
        for t, hid in destroyed:
            pts = (150 if t.bonus else 100) + 10 * m.n
            self.points += pts
            if hid:
                t.hidden = False
                t.seen = True
                self.say(f"SEKUNDAREXPLOSION! OKAND KONTAKT MAL {t.letter} ({t.name}) "
                         f"UTSLAGEN! +{pts} POANG", "ok")
            else:
                self.say(f"{who}: MAL {t.letter} ({t.name}) UTSLAGET! +{pts} POANG", "ok")
        if destroyed:
            self.reselect()

    def light_impact(self, ix, iy, r, n, off, where):
        m = self.m
        m.lit.append((ix, iy, r))
        self.say(f"LJUS: O{ix:.1f} N{iy:.1f} BELYST ({r} M RADIE). {off} ({where}).", "hi")
        found = []
        for t in m.targets:
            if t.alive and math.hypot(ix - t.x, iy - t.y) <= r:
                new = t.hidden
                t.hidden = False
                t.seen = True
                found.append((t, new))
        if m.friend and math.hypot(ix - m.friend[0], iy - m.friend[1]) <= r:
            m.friend_seen = True
            self.say("  EGNA TRUPPER SYNS INOM OMRADET.", "fo")
        for t, new in found:
            d = math.hypot(t.x - ix, t.y - iy)
            self.say(f"  {'NY KONTAKT: ' if new else ''}MAL {t.letter} ({t.name}) "
                     f"O{t.x:.1f} N{t.y:.1f} - {d:.0f} M {compass(t.x - ix, t.y - iy)} "
                     f"OM LJUSET", "ok" if new else "fo")
        if not found:
            self.say("  INGA FIENDER INOM DET BELYSTA OMRADET.", "n")
        newc = sum(1 for _, new in found if new)
        self.report = (f"LJUS {n} O{ix:.1f} N{iy:.1f}: {len(found)} FIENDER"
                       + (f", {newc} NYA" if newc else ""))

    def end_mission(self, msg, ok):
        self.state = "end"
        self.shop_open = False
        self.p["run_done"] += 1
        if self.trust <= 0:
            self.gameover = True
            self.p["best"] = max(self.p["best"], self.p["run_done"])
            self.p["run_done"] = 0
            self.p["trust"] = 3
            self.endmsg = (f"{msg} FORTROENDET SLUT. REKORD {self.p['best']} UPPDRAG. "
                           f"POANG OCH UPPGRADERINGAR BEHALLS. ENTER = NY OMGANG")
        else:
            self.p["best"] = max(self.p["best"], self.p["run_done"])
            self.endmsg = f"{msg} ENTER = NASTA UPPDRAG (BUTIK = KOP)"
        self.save()

    # ----- kommandon -----
    def run(self, line):
        t = line.upper().replace(",", ".").split()
        i = 0
        m = self.m
        while i < len(t):
            c = t[i]
            i += 1
            if c in ("Q", "SLUT", "EXIT", "AVSLUTA"):
                return True
            if c in ("TUTORIAL", "INTRO") and i < len(t) and t[i] in ("AV", "OFF", "PA", "ON"):
                self.p["tutorial_auto"] = t[i] in ("PA", "ON")
                self.save()
                self.say("TUTORIAL VISAS " + ("VID VARJE START." if self.p["tutorial_auto"]
                                               else "INTE LANGRE VID START (? FUNGERAR)."), "ok")
                i += 1
                continue
            if c in ("HJALP", "HELP", "?", "H", "TUTORIAL", "INTRO"):
                self.open_tutorial()
                break
            elif c == "BUTIK":
                self.shop_open = not self.shop_open
            elif c in ("KOP", "KOPA"):
                if i >= len(t) or not t[i].isdigit():
                    self.say("SKRIV KOP <NUMMER>, T.EX. KOP 1", "bad")
                    break
                self.buy(int(t[i]))
                i += 1
            elif c == "SPARA":
                ok = self.save()
                self.say("SPARAT." if ok else "KUNDE INTE SPARA FILEN.",
                         "ok" if ok else "bad")
            elif c == "NOLLSTALL":
                if i < len(t) and t[i] == "JA":
                    self.p = dict(DEFAULT_PROFILE)
                    self.save()
                    self.say("ALL PROGRESS RADERAD.", "bad")
                    self.new_mission()
                    self.tut = 0
                    return False
                self.say("SKRIV NOLLSTALL JA FOR ATT RADERA ALL PROGRESS.", "bad")
                break
            elif c in AMMO_TYPES:
                self.set_ammo(c)
            elif c in ("AMMO", "GRAN", "GRANAT", "TYP"):
                if i >= len(t) or t[i] not in AMMO_TYPES:
                    self.say("VALJ HE, APHE, FRAG, HEAT ELLER LJUS.", "bad")
                    break
                self.set_ammo(t[i])
                i += 1
            elif c in ("ELD", "FIRE", "SKJUT"):
                self.fire()
                break
            elif c == "KORR":
                self.korr()
            elif c in ("NASTA", "NEXT", "FORRA", "PREV"):
                if self.state != "aim":
                    self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
                    break
                self.step_target(1 if c in ("NASTA", "NEXT") else -1)
            elif c == "MAL":
                if self.state != "aim":
                    self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
                    break
                if i >= len(t):
                    self.say("SKRIV MAL <BOKSTAV>, T.EX. MAL A", "bad")
                    break
                ok = self.select_target(t[i])
                i += 1
                if not ok:
                    break
            elif c in ("PUNKT", "LANDA", "SIKTA"):
                if self.state != "aim":
                    self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
                    break
                letter = None
                if i < len(t) and len(t[i]) == 1 and t[i] in LETTERS:
                    letter = t[i]
                    i += 1
                nums = []
                while i < len(t) and len(nums) < 2 and num(t[i]) is not None:
                    nums.append(num(t[i]))
                    i += 1
                if len(nums) == 1:
                    self.say("PUNKT KRAVER TVA TAL: OST NORR (ELLER OFFSET OST NORR).", "bad")
                    break
                if letter is not None:
                    if not self.select_target(letter):
                        break
                    tgt = self.cur
                    ox, oy = nums if nums else (0.0, 0.0)
                    ax, ay = tgt.x + ox, tgt.y + oy
                    label = f"MAL {tgt.letter}" + (f" {ox:+.0f}/{oy:+.0f}" if nums else "")
                elif nums:
                    ax, ay = nums
                    label = "PUNKT"
                else:
                    tgt = self.cur
                    ax, ay = tgt.x, tgt.y
                    label = f"MAL {tgt.letter}"
                if not self.set_solution(ax, ay, label):
                    break
            elif c in ("AZ", "AZIMUT", "EL", "ELEV", "ELEVATION", "LAD", "LADDNING"):
                if self.state != "aim":
                    self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
                    break
                if i >= len(t):
                    self.say(f"SAKNAR VARDE FOR {c}.", "bad")
                    break
                val = num(t[i])
                if val is None:
                    self.say(f"OGILTIGT VARDE: {t[i]}", "bad")
                    break
                i += 1
                self.aim = None          # manuell inmatning ersatter PUNKT-losningen
                if c.startswith("AZ"):
                    self.az = round(val % 360, 3)
                elif c.startswith("EL"):
                    if not 5 <= val <= 85:
                        self.say("ELEVATION MASTE VARA 5-85 GRADER.", "bad")
                        break
                    self.elev = round(val, 3)
                else:
                    if int(val) not in CHARGES:
                        self.say("LADDNING MASTE VARA 1, 2 ELLER 3.", "bad")
                        break
                    self.charge = int(val)
                    self.charge_auto = False
                    self.show_table()
            else:
                self.say(f"OKAND KOMMANDO: {c}  (SKRIV ? FOR HJALP)", "bad")
                break
        return False

    def show_table(self):
        v = CHARGES[self.charge]
        t = self.cur
        e = elev_for(v, t.dist)
        if e is None:
            self.say(f"TABELL: LADDNING {self.charge} NAR INTE {t.dist:.0f} M "
                     f"(MAX {rng_for(v, 45):.0f} M).", "bad")
        else:
            self.say(f"TABELL: LAD {self.charge}, MAL {t.letter} {t.dist:.1f} M => EL {e:.2f} "
                     f"(UTAN VIND). SKRIV PUNKT FOR EXAKT LOSNING MED VIND.", "hi")


# ---------- ritning ----------
def put(scr, y, x, s, attr=0):
    h, w = scr.getmaxyx()
    if y < 0 or y >= h or x >= w or x < 0:
        return
    s = s[:w - x - (1 if y == h - 1 else 0)]
    try:
        scr.addstr(y, x, s, attr)
    except curses.error:
        pass


def draw_tutorial(scr, g):
    h, w = scr.getmaxyx()
    GREEN = curses.color_pair(1)
    G_B = GREEN | curses.A_BOLD
    YEL = curses.color_pair(3) | curses.A_BOLD
    bw = min(w - 6, 104)
    bh = h - 4
    bx = (w - bw) // 2
    by = 2
    for y in range(by, by + bh):
        put(scr, y, bx, " " * bw, GREEN)
    put(scr, by, bx, "+" + "-" * (bw - 2) + "+", G_B)
    put(scr, by + bh - 1, bx, "+" + "-" * (bw - 2) + "+", G_B)
    for y in range(by + 1, by + bh - 1):
        put(scr, y, bx, "|", G_B)
        put(scr, y, bx + bw - 1, "|", G_B)
    title, items = TUTORIAL[g.tut]
    put(scr, by + 1, bx + 3, f"TUTORIAL - {title}", G_B)
    put(scr, by + 1, bx + bw - 14, f"SIDA {g.tut + 1}/{len(TUTORIAL)}", G_B)
    inner = bw - 6
    lines = []                       # (x-offset | "row", text, attr | text2)
    for item in items:
        if isinstance(item, tuple):
            cmd, desc = item
            for j, ln in enumerate(textwrap.wrap(desc, max(10, inner - 20)) or [""]):
                if j == 0:
                    lines.append(("row", cmd, ln))      # kommando + forsta radens text
                else:
                    lines.append((20, ln, GREEN))
        else:
            for ln in textwrap.wrap(item, inner - 2, initial_indent="- ",
                                    subsequent_indent="  "):
                lines.append((0, ln, GREEN))
    top = by + 3
    room = (by + bh - 3) - top
    max_scroll = max(0, len(lines) - room)
    g.tut_scroll = min(g.tut_scroll, max_scroll)
    y = top
    for entry in lines[g.tut_scroll:g.tut_scroll + room]:
        if entry[0] == "row":
            put(scr, y, bx + 3, entry[1], YEL)
            put(scr, y, bx + 3 + 20, entry[2], GREEN)
        else:
            put(scr, y, bx + 3 + entry[0], entry[1], entry[2])
        y += 1
    if max_scroll:
        more = []
        if g.tut_scroll > 0:
            more.append("PIL UPP = MER ^")
        if g.tut_scroll < max_scroll:
            more.append("PIL NER = MER v")
        put(scr, by + 2, bx + bw - 3 - 32, "  ".join(more).rjust(32), YEL)
    last = g.tut + 1 >= len(TUTORIAL)
    nxt = "ENTER/KLICK = BORJA SPELA" if last else "ENTER/KLICK = NASTA"
    put(scr, by + bh - 2, bx + 3,
        f"{nxt}    PIL VANSTER = TILLBAKA    S = HOPPA OVER", YEL)


def draw(scr, g):
    scr.erase()
    h, w = scr.getmaxyx()
    GREEN = curses.color_pair(1)
    RED_N = curses.color_pair(2)
    RED = RED_N | curses.A_BOLD
    YEL_N = curses.color_pair(3)
    YEL = YEL_N | curses.A_BOLD
    CYAN = curses.color_pair(4) | curses.A_BOLD
    G_B = GREEN | curses.A_BOLD
    kinds = {"n": GREEN, "hi": G_B, "bad": RED, "ok": YEL, "fo": CYAN}
    m = g.m
    panel_x = w - 37
    maxw = panel_x - 3

    def pl(y, x, s, attr=0):          # vanster inforuta, klipps for panelen
        put(scr, y, x, s[:max(0, maxw - x)], attr)

    # ---- fast inforuta (vanster, ligger kvar hela tiden) ----
    put(scr, 0, 1, "ELDLEDNINGSCENTRAL // IRON NEST", G_B)
    put(scr, 0, 40, f"UPPDRAG {g.mn}   POANG {g.points}   "
                    f"FORTROENDE {'#' * g.trust}", G_B)
    row = 1
    for i, t in enumerate(m.targets):
        if t.hidden:
            continue
        mark = ">" if i == g.sel else " "
        star = "*" if t.bonus else " "
        if t.alive:
            stv = f"{t.hp}%" if (g.spotter or t.seen) else "??"
            line = (f"{mark}{t.letter}{star}{t.name:<16} {SKYDD_KORT[t.hard]:<6} "
                    f"O{t.x:5.0f} N{t.y:5.0f} {t.dist:5.0f}M AZ{t.bearing:7.2f} {stv:>4}")
            pl(row, 1, line, RED if i == g.sel else RED_N)
        else:
            pl(row, 1, f"{mark}{t.letter}{star}{t.name:<16} UTSLAGET", GREEN)
        row += 1
    c = g.cur
    pl(row, 1, f"VALT MAL {c.letter}: O {c.x:.1f}  N {c.y:.1f}  AVST {c.dist:.1f} M  "
               f"AZ {c.bearing:.3f}", G_B)
    row += 1
    wl = f"VIND {m.wind:.1f} M/S FRAN {m.wfrom:03d} (MATFEL +/-{WIND_ERR:.1f})"
    if g.wcorr != (0.0, 0.0):
        wl += f"  KORR O{g.wcorr[0]:+.2f} N{g.wcorr[1]:+.2f}"
    pl(row, 1, wl, G_B)
    row += 1
    if m.friend:
        safe = " ".join(f"{k}{v['safe']}" for k, v in AMMO_TYPES.items() if v["safe"])
        pl(row, 1, f"EGNA O{m.friend[0]:.1f} N{m.friend[1]:.1f}  SAKERHET {safe}", CYAN)
        row += 1
    az = "--" if g.az is None else f"{g.az:.2f}"
    el = "--" if g.elev is None else f"{g.elev:.2f}"
    ch = "--" if g.charge is None else str(g.charge)
    am = "--" if g.ammo_type is None else g.ammo_type
    inst = f"INSTALLT: AZ {az}  EL {el}  LAD {ch}  GRAN {am}"
    if g.aim:
        inst += f"  SIKT O{g.aim[0]:.1f} N{g.aim[1]:.1f}"
    pl(row, 1, inst, YEL)
    row += 1
    if None not in (g.az, g.elev, g.charge):
        v = CHARGES[g.charge]
        px, py, T = predict(g.az, g.elev, v, g.wvec_eff())
        ref = g.aim or (c.x, c.y)
        dev = math.hypot(px - ref[0], py - ref[1])
        spec = AMMO_TYPES[g.ammo_type or "HE"]
        mult = (0.85 ** g.p["optics"]) * spec["prec"]
        R = rng_for(v, g.elev)
        sr = SPREAD_R * R * mult
        sl = R * math.radians(SPREAD_AZ) * mult
        pl(row, 1, f"BERAKNAT O{px:.1f} N{py:.1f} AVV {dev:.1f} M  TID {T:.1f} S  "
                   f"SPR +/-{sr:.0f}/{sl:.0f} M", YEL)
    else:
        pl(row, 1, "BERAKNAT: -- (SKRIV PUNKT, ELLER SATT AZ, EL OCH LAD)", GREEN)
    row += 1
    sp = "SPEJARE: JA" if g.spotter else "SPEJARE: NEJ"
    pl(row, 1, f"{sp}  RAPPORT: {g.report}", CYAN)
    sep = row + 1
    put(scr, sep, 0, "-" * (panel_x - 2), GREEN)
    put(scr, sep, 2, " TAB = NASTA MAL  * = BONUS  G kanon  # egna  . belyst ", GREEN)

    # ---- karta ----
    mx0, my0 = 3, sep + 1
    mw = panel_x - 2 - mx0
    mh = (h - 7) - my0

    def cell(x, y):
        if not (0 <= x <= MAP_M and 0 <= y <= MAP_M):
            return None
        cc = mx0 + int(x / MAP_M * (mw - 1) + 0.5)
        r = my0 + (mh - 1) - int(y / MAP_M * (mh - 1) + 0.5)
        return r, cc

    if mh >= 3:
        # belysta omraden (LJUS)
        for lx, ly, lr in m.lit:
            for r0 in range(my0, my0 + mh):
                for c0 in range(mx0, mx0 + mw):
                    wx_ = (c0 - mx0) / (mw - 1) * MAP_M
                    wy_ = (my0 + mh - 1 - r0) / (mh - 1) * MAP_M
                    if math.hypot(wx_ - lx, wy_ - ly) <= lr:
                        put(scr, r0, c0, ".", YEL_N)
        for k in range(7):
            km = k * 1000.0
            pc = cell(km, 0)
            if pc:
                put(scr, my0 + mh, pc[1], str(k), GREEN)
            pr = cell(0, km)
            if pr:
                put(scr, pr[0], 1, str(k), GREEN)
            for k2 in range(7):
                p = cell(km, k2 * 1000.0)
                if p:
                    put(scr, p[0], p[1], "+", GREEN)
        put(scr, my0 + mh, mx0 + mw - 6, "KM", GREEN)

        p = cell(*GUN)
        if p:
            put(scr, p[0], p[1], "G", G_B)
        for i, (ix, iy, shown) in enumerate(m.impacts):
            if not shown:
                continue
            p = cell(ix, iy)
            if p:
                put(scr, p[0], p[1], str((i + 1) % 10), YEL)
        if g.aim:
            p = cell(*g.aim)
            if p:
                put(scr, p[0], p[1], "+", YEL)
        for t in m.targets:
            if t.hidden or not (g.spotter or t.seen):
                continue
            p = cell(t.x, t.y)
            if p:
                put(scr, p[0], p[1], t.letter if t.alive else "x",
                    RED if t.alive else GREEN)
        if m.friend and (g.spotter or m.friend_seen):
            p = cell(*m.friend)
            if p:
                put(scr, p[0], p[1], "#", CYAN)

    # ---- skjuttabell + granattabell till hoger ----
    L = [("SKJUTTABELL (EL, UTAN VIND)", G_B),
         ("AVST    L1     L2     L3", GREEN)]
    for r in range(1500, 5501, 500):
        line = f"{r:4d}"
        for cc in (1, 2, 3):
            e = elev_for(CHARGES[cc], r)
            line += "   --  " if e is None or e < 5 else f"  {e:5.1f}"
        L.append((line, GREEN))
    L += [("", GREEN),
          ("GRANATER (SKADA % PER TRAFF)", G_B),
          (f"{'TYP':<5}{'KVAR':>4}{'RAD':>5}{'MJUK':>6}{'PANS':>5}{'BUNK':>5}", GREEN)]
    for name, spec in AMMO_TYPES.items():
        d = spec["dmg"]
        L.append((f"{name:<5}{m.stock[name]:>4}{spec['radius']:>4}m"
                  f"{d['mjuk']:>5}%{d['pansar']:>4}%{d['bunker']:>4}%",
                  YEL if g.ammo_type == name else GREEN))
    y = 1
    for text, attr in L:
        if y >= h - 7:
            break
        put(scr, y, panel_x, text, attr)
        y += 1

    # ---- butik (ruta ovanpa kartan) ----
    if g.shop_open:
        bw = 58
        bx = max(1, mx0 + (mw - bw) // 2)
        by = my0
        title = f"+- BUTIK " + "-" * 30 + f" POANG {g.points} "
        put(scr, by, bx, title.ljust(bw - 1, "-")[:bw - 1] + "+", G_B)
        for i, (label, price) in enumerate(SHOP):
            status, ok = g.shop_status(i)
            line = f" {i + 1} {label:<33}{price:>5}  {status}"
            attr = G_B if (ok and g.points >= price) else GREEN
            put(scr, by + 1 + i, bx, "|" + line.ljust(bw - 2)[:bw - 2] + "|", attr)
        r0 = by + 1 + len(SHOP)
        put(scr, r0, bx, "|" + " KOP <NR> = KOP     BUTIK = STANG".ljust(bw - 2) + "|", YEL)
        put(scr, r0 + 1, bx, "+" + "-" * (bw - 2) + "+", G_B)

    # ---- logg + kommandorad langst ner ----
    rows = g.log[-4:]
    for i, (text, kind) in enumerate(rows):
        put(scr, h - 6 + i, 0, text, kinds.get(kind, GREEN))
    put(scr, h - 2, 0, "-" * (w - 1), GREEN)
    if g.state == "flight":
        put(scr, h - 1, 0, f"GRANAT I LUFTEN...  NEDSLAG OM {max(0, g.t_left):.1f} S", YEL)
    elif g.state == "end":
        put(scr, h - 1, 0, g.endmsg + "  > " + g.buf + "_", YEL)
    else:
        put(scr, h - 1, 0, "KOMMANDO> " + g.buf + "_", G_B)
    if g.tut is not None:
        draw_tutorial(scr, g)
    scr.refresh()


def main(scr):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    curses.start_color()
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
    scr.bkgd(" ", curses.color_pair(1))
    scr.timeout(50)
    try:
        scr.keypad(True)
    except curses.error:
        pass
    g = Game()
    last = time.monotonic()
    mouse_on = False
    try:
        while True:
            h, w = scr.getmaxyx()
            now = time.monotonic()
            dt = min(0.2, now - last)
            last = now
            want_mouse = g.tut is not None          # mus bara under tutorialen
            if want_mouse != mouse_on:
                mouse_on = want_mouse
                try:
                    curses.mousemask(curses.ALL_MOUSE_EVENTS if want_mouse else 0)
                except (curses.error, AttributeError):
                    pass
            k = scr.getch()
            if k == curses.KEY_MOUSE:
                try:
                    bstate = curses.getmouse()[4]
                    clicked = bool(bstate & (getattr(curses, "BUTTON1_CLICKED", 0)
                                             | getattr(curses, "BUTTON1_PRESSED", 0)))
                except curses.error:
                    clicked = False
                if clicked:
                    g.click()
                continue
            if k == curses.KEY_RESIZE:
                if os.name == "nt":                 # Windows (PDCurses)
                    try:
                        curses.resize_term(0, 0)
                    except curses.error:
                        pass
                continue
            if h < MIN_H or w < MIN_W:
                scr.erase()
                put(scr, 0, 0, f"Gor terminalen storre (minst {MIN_W}x{MIN_H}, "
                               f"nu {w}x{h})")
                scr.refresh()
                if k in (ord("q"), ord("Q")):
                    return
                continue
            if k != -1:
                if g.key(k):
                    return
            g.update(dt)
            draw(scr, g)
    finally:
        g.save()


def ensure_curses():
    """Pa Windows saknas curses; erbjud att installera windows-curses."""
    global curses
    if curses is not None:
        return True
    if os.name == "nt":
        print("Windows har inte Pythons curses-modul inbyggd.")
        print("Spelet behover paketet 'windows-curses'.")
        ans = input("Installera det nu med pip? (j/n): ").strip().lower()
        if ans in ("j", "ja", "y", "yes"):
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                       "windows-curses"])
                import importlib
                curses = importlib.import_module("curses")
                return True
            except Exception as ex:                 # noqa: BLE001
                print("Installationen misslyckades:", ex)
        print("Installera manuellt med:  python -m pip install windows-curses")
        print("Om pip sager att inget passande hittas ar din Python for ny")
        print("(windows-curses finns for Python 3.9-3.13). Installera Python 3.13:")
        print("  winget install Python.Python.3.13")
        print("och starta sedan spelet med:  py -3.13 eldledning.py")
    else:
        print("Python-modulen 'curses' saknas pa den har datorn.")
    return False


if __name__ == "__main__":
    if ensure_curses():
        try:
            curses.wrapper(main)
        except KeyboardInterrupt:
            pass
