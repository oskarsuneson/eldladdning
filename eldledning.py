#!/usr/bin/env python3
"""
ELDLEDNINGSCENTRAL // IRON NEST-stil (WarGames, gront pa svart)

Fungerar pa Linux, macOS och Windows (Windows behover paketet windows-curses;
spelet erbjuder att installera det at dig vid forsta start).

Du styr en artilleripjas. Varje uppdrag har ETT ELLER FLERA mal (A, B, C, D).
Du far underrattelser om vad och var. Utan spejare syns varken mal eller
nedslag pa kartan och ingen rapporterar var granaterna landar. Kop en spejare
i BUTIKEN med dina poang. Poang och uppgraderingar sparas automatiskt
(fil: .eldledning_save.json i din hemmapp).

En tutorial visas forsta gangen du startar. Tryck ENTER eller klicka for att
bladdra, S for att hoppa over. Skriv TUTORIAL i spelet for att se den igen.

Starta:
  Linux / macOS:   python3 eldledning.py
  Windows:         python eldledning.py
Terminalen ska vara minst 110 tecken bred och 30 rader hog.

Kommandon (flera pa samma rad ar ok):
  MAL B       valj vilket mal du siktar pa (A-D)
  AZ 28.3     satt azimut (grader, 0 = norr, 90 = ost)
  EL 41.7     satt elevation (grader)
  LAD 2       valj laddning 1-3 (visar tabellens elevation for valt mal)
  HE / APHE   valj granattyp
  ELD         skjut
  KORR        FDC raknar korrektion fran spejarens senaste rapport
  BUTIK       oppna/stang butiken      KOP 1   kop sak nummer 1
  SPARA       spara nu                 NOLLSTALL JA   radera all progress
  ?           visa tutorialen igen     Q       spara och avsluta
              (TUTORIAL och HJALP fungerar ocksa)
Exempel:  MAL A AZ 28.3 EL 41.7 LAD 2 APHE ELD
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
FRIEND_R = 100.0
SAVE = os.path.join(os.path.expanduser("~"), ".eldledning_save.json")

# Granattyper: radie (m) inom vilken en traff ger skada, skada i % per traff
# mot olika skydd, och antal granater per uppdrag (utan uppgraderingar).
AMMO_TYPES = {
    "HE":   dict(radius=60, stock=6, dmg={"mjuk": 100, "pansar": 25, "bunker": 15}),
    "APHE": dict(radius=30, stock=5, dmg={"mjuk": 40, "pansar": 100, "bunker": 60}),
}
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
LETTERS = "ABCD"

# Butiken: (namn, pris)
SHOP = [
    ("SPEJARE (DETTA UPPDRAG)", 150),
    ("FAST SPEJARE (ALLA UPPDRAG)", 1200),
    ("EXTRA HE +1 PER UPPDRAG", 250),
    ("EXTRA APHE +1 PER UPPDRAG", 300),
    ("PRECISIONSOPTIK -15% SPRIDNING", 400),
    ("FORTROENDE +1", 500),
]

# Tutorial: lista av (rubrik, rader). En rad ar antingen text eller (kommando, forklaring).
TUTORIAL = [
    ("SPELIDEEN", [
        "Du styr en artilleripjas (G pa kartan). Varje uppdrag har ett eller flera mal, A till D.",
        "Underrattelsetjansten talar om VAD och VAR: koordinater, avstand, azimut och hur "
        "skyddat malet ar.",
        "Din uppgift: berakna riktning (AZ), lutning (EL) och laddning (LAD), valj granat "
        "(HE eller APHE) och skjut (ELD).",
        "Vind och slumpmassig spridning gor att forsta skottet sallan landar exakt. "
        "Justera och skjut igen.",
        "Sla ut ALLA mal innan granaterna tar slut - utan att traffa egna trupper (F).",
        "Misslyckas du eller traffar egna trupper tappar du fortroende. Nar det ar slut "
        "borjar en ny omgang (poang och uppgraderingar behalls).",
        "Utan spejare syns varken mal eller nedslag pa kartan och du far inga "
        "nedslagsrapporter. Kop en spejare i BUTIKEN.",
    ]),
    ("KOMMANDON", [
        ("MAL A", "Valj vilket mal (A-D) du siktar pa. Pilen > i listan visar valt mal."),
        ("AZ 28.3", "Azimut = riktning i sidled, i grader. 0 = norr, 90 = ost. "
                    "Malets azimut star i listan."),
        ("EL 41.7", "Elevation = pipans lutning, 5-85 grader. Styr hur LANGT granaten flyger."),
        ("LAD 2", "Laddning 1-3 (mer kraft = lagre vinkel). Visar vilken EL valt mal kraver."),
        ("HE", "Sprangranat: stor radie (60 m). Bra mot oskyddat, svag mot pansar och bunker."),
        ("APHE", "Pansarbrytande: liten radie (30 m). Bra mot pansar och bunker."),
        ("ELD", "Skjut. Kraver AZ, EL, LAD och vald granat."),
        ("KORR", "FDC raknar om AZ och EL fran spejarens senaste rapport (kraver spejare)."),
        ("BUTIK", "Oppna/stang butiken. KOP 1 kopar vara nummer 1 (kraver poang)."),
        ("SPARA", "Spara direkt. Spelet sparar ocksa automatiskt efter varje uppdrag och kop."),
        ("? eller TUTORIAL", "Visa den har hjalpen igen (tryck ? pa tom rad, eller skriv HJALP)."),
        ("TUTORIAL AV / PA", "Stang av / satt pa att tutorialen visas automatiskt vid varje start."),
        ("NOLLSTALL JA", "Radera ALL sparad progress."),
        ("Q", "Spara och avsluta."),
        "Tips: flera kommandon pa en rad, t.ex.  MAL A AZ 28.3 EL 41.7 LAD 2 APHE ELD",
    ]),
    ("SKARMEN", [
        "Overst: listan med mal (skydd, koordinater O=ost N=norr, avstand, azimut, styrka %), "
        "vind, egna trupper, dina installningar och senaste rapport.",
        "Mitten: kartan. G = din pjas, A-D = mal, x = utslaget mal, F = egna trupper, "
        "siffror = dina nedslag. Mal, F och nedslag syns bara om du har spejare.",
        "Hoger: skjuttabell (elevation per avstand och laddning) och granattabell "
        "(antal kvar, radie, skada i % mot oskyddat/pansar/bunker).",
        "Langst ner: de senaste meddelandena och kommandoraden KOMMANDO>.",
        "Vinden knuffar granaten at det hall den blaser mot. Vinden anges som FRAN en "
        "riktning i grader.",
        "Mal som ligger tatt kan traffas av samma granat. Egna trupper (F) far aldrig "
        "traffas inom 100 m.",
    ]),
    ("TIPS, POANG OCH BUTIK", [
        "Forsta skottet: satt AZ till malets azimut, valj LAD och las av EL. Skjut och "
        "las rapporten.",
        "'FOR LANGT' / 'FOR KORT' rattas med EL. 'TILL HOGER' / 'TILL VANSTER' rattas med "
        "AZ. KORR gor det at dig.",
        "Oskyddat -> HE. Pansar och bunker -> APHE (en bunker kraver flera traffar).",
        "Poang far du for varje utslaget mal plus bonus for granater kvar. De anvands i butiken.",
        "Butiken: spejare for ett uppdrag (150), fast spejare (1200), extra HE (250), extra "
        "APHE (300), precisionsoptik (400), fortroende +1 (500).",
        "Uppdrag 1 har gratis spejare sa du kan ova. Darefter kopar du spejare i butiken.",
        "Spelet sparas i filen .eldledning_save.json i din hemmapp.",
        "Tryck ? nar som helst for att se den har tutorialen igen.",
        "Tryck ENTER eller klicka for att borja. Lycka till!",
    ]),
]

MIN_W, MIN_H = 110, 30

DEFAULT_PROFILE = dict(points=0, run_done=0, trust=3, best=0, won=0,
                       he_extra=0, aphe_extra=0, optics=0, perm_spotter=False,
                       tutorial_done=False, tutorial_auto=True)


def enter_keys():
    return (10, 13, curses.KEY_ENTER, getattr(curses, "PADENTER", 459))


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
    p["he_extra"] = min(4, max(0, int(p["he_extra"])))
    p["aphe_extra"] = min(3, max(0, int(p["aphe_extra"])))
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


# ---------- uppdrag ----------
class Target:
    def __init__(self, letter, name, hard, x, y):
        self.letter = letter
        self.name = name
        self.hard = hard
        self.x = x
        self.y = y
        self.hp = 100
        dx, dy = x - GUN[0], y - GUN[1]
        self.dist = math.hypot(dx, dy)
        self.bearing = math.degrees(math.atan2(dx, dy)) % 360

    @property
    def alive(self):
        return self.hp > 0


def place_targets(count):
    """Slumpar positioner. Ibland ligger mal tatt ihop sa en HE kan traffa flera."""
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
        extra = 2 * (len(self.targets) - 1)
        self.stock = {k: v["stock"] + extra for k, v in AMMO_TYPES.items()}
        self.stock["HE"] += prof["he_extra"]
        self.stock["APHE"] += prof["aphe_extra"]
        self.wind = random.randint(0, min(10, 2 + n))
        self.wfrom = random.randint(0, 359)
        self.friend = None
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
        self.impacts = []

    def total_ammo(self):
        return sum(self.stock.values())

    def wind_vec(self):
        th = math.radians(self.wfrom + 180)      # vinden blaser TILL
        return self.wind * math.sin(th), self.wind * math.cos(th)


def describe(ra, rc):
    parts = []
    if ra > 0:
        parts.append(f"{ra} M FOR LANGT")
    elif ra < 0:
        parts.append(f"{-ra} M FOR KORT")
    if rc > 0:
        parts.append(f"{rc} M TILL HOGER")
    elif rc < 0:
        parts.append(f"{-rc} M TILL VANSTER")
    return ", ".join(parts) or "PRECIS PA MALET"


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

    def new_mission(self):
        self.mn = self.p["run_done"] + 1
        self.m = Mission(self.mn, self.p)
        self.sel = 0
        self.az = None
        self.elev = None
        self.charge = None
        self.ammo_type = None
        self.shot_type = None
        self.shot_target = 0
        self.last = None
        self.state = "aim"
        self.endmsg = ""
        self.gameover = False
        self.shop_open = False
        free = self.mn == 1
        self.spotter = self.p["perm_spotter"] or free
        m = self.m
        nt = len(m.targets)
        self.say(f"--- UPPDRAG {self.mn}: {nt} MAL ---", "hi")
        who = "SPEJARE" if self.spotter else "UNDERRATTELSE"
        if nt == 1:
            self.say(f"{who}: ELDUPPDRAG! {m.targets[0].name}, "
                     f"{SKYDD[m.targets[0].hard]}. SE LISTAN OVAN.", "fo")
        else:
            self.say(f"{who}: ELDUPPDRAG! {nt} MAL (A-{LETTERS[nt - 1]}), SE "
                     f"LISTAN OVAN. VALJ MAL MED 'MAL A'. ALLA MASTE SLAS UT.", "fo")
        self.say(f"VIND {m.wind} M/S FRAN {m.wfrom:03d} GRADER. "
                 f"GRANATER: {self.stock_text()}.", "fo")
        if m.friend:
            self.say(f"VARNING: EGNA TRUPPER VID OST {m.friend[0]:04.0f} "
                     f"NORR {m.friend[1]:04.0f}. FAR EJ TRAFFAS "
                     f"(NARMARE AN {FRIEND_R:.0f} M).", "bad")
        if self.spotter:
            if free and not self.p["perm_spotter"]:
                self.say("SPEJARE PA PLATS (GRATIS UPPDRAG 1).", "ok")
            self.report = "INGEN ANNU"
        else:
            self.say("INGEN SPEJARE PA PLATS: MAL OCH NEDSLAG SYNS EJ PA KARTAN. "
                     "SKRIV BUTIK FOR ATT KOPA EN.", "bad")
            self.report = "INGEN SPEJARE - NEDSLAG OBSERVERAS EJ"
        self.say_fdc()
        self.say("VALJ GRANAT (HE/APHE). SKRIV HJALP FOR KOMMANDON.", "hi")

    def say_fdc(self):
        t = self.cur
        self.say(f"FDC: MAL {t.letter} ({t.name}): AZIMUT {t.bearing:.1f}, "
                 f"AVSTAND {t.dist:.0f} M.", "hi")

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
        if i == 2:
            return f"{p['he_extra']}/4", p["he_extra"] < 4
        if i == 3:
            return f"{p['aphe_extra']}/3", p["aphe_extra"] < 3
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
        elif i == 2:
            p["he_extra"] += 1
            if live:
                self.m.stock["HE"] += 1
        elif i == 3:
            p["aphe_extra"] += 1
            if live:
                self.m.stock["APHE"] += 1
        elif i == 4:
            p["optics"] += 1
        elif i == 5:
            p["trust"] += 1
        self.say(f"KOPT: {label} (-{price} POANG). KVAR {self.points}.", "ok")
        self.save()

    # ----- kommandon -----
    def key(self, k):
        if self.tut is not None:
            self.tut_key(k)
            return False
        back_keys = (127, 8, curses.KEY_BACKSPACE)
        if k == ord("?") and not self.buf and self.state != "flight":
            self.open_tutorial()          # ? pa tom rad oppnar tutorialen direkt
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
        self.say(f"GRANAT: {name}. RADIE {spec['radius']} M. "
                 f"{self.m.stock[name]} KVAR.", "hi")

    def select_target(self, tok):
        idx = None
        if tok and tok[0] in LETTERS[:len(self.m.targets)] and len(tok) == 1:
            idx = LETTERS.index(tok[0])
        elif tok.isdigit() and 1 <= int(tok) <= len(self.m.targets):
            idx = int(tok) - 1
        if idx is None:
            self.say(f"OGILTIGT MAL. VALJ A-{LETTERS[len(self.m.targets) - 1]}.", "bad")
            return False
        if not self.m.targets[idx].alive:
            self.say(f"MAL {LETTERS[idx]} AR REDAN UTSLAGET.", "bad")
            return False
        if idx != self.sel:
            self.sel = idx
            self.last = None
        self.say_fdc()
        return True

    def reselect(self):
        if self.cur.alive:
            return
        for i, t in enumerate(self.m.targets):
            if t.alive:
                self.sel = i
                self.last = None
                return

    def run(self, line):
        t = line.upper().replace(",", ".").split()
        i = 0
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
                    self.say("VALJ HE ELLER APHE.", "bad")
                    break
                self.set_ammo(t[i])
                i += 1
            elif c in ("ELD", "FIRE", "SKJUT"):
                self.fire()
                break
            elif c == "KORR":
                self.korr()
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
            elif c in ("AZ", "AZIMUT", "EL", "ELEV", "ELEVATION",
                       "LAD", "LADDNING"):
                if self.state != "aim":
                    self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
                    break
                if i >= len(t):
                    self.say(f"SAKNAR VARDE FOR {c}.", "bad")
                    break
                try:
                    val = float(t[i])
                except ValueError:
                    self.say(f"OGILTIGT VARDE: {t[i]}", "bad")
                    break
                i += 1
                if c.startswith("AZ"):
                    self.az = round(val % 360, 2)
                elif c.startswith("EL"):
                    if not 5 <= val <= 85:
                        self.say("ELEVATION MASTE VARA 5-85 GRADER.", "bad")
                        break
                    self.elev = round(val, 2)
                else:
                    if int(val) not in CHARGES:
                        self.say("LADDNING MASTE VARA 1, 2 ELLER 3.", "bad")
                        break
                    self.charge = int(val)
                    self.show_table()
            else:
                self.say(f"OKAND KOMMANDO: {c}  (SKRIV HJALP)", "bad")
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
            self.say(f"TABELL: LADDNING {self.charge}, MAL {t.letter} "
                     f"{t.dist:.0f} M => ELEV {e:.1f}", "hi")

    def korr(self):
        if not self.spotter:
            self.say("FDC: INGEN SPEJARE - INGA RAPPORTER ATT KORRIGERA MOT.", "bad")
            return
        if not self.last or None in (self.az, self.elev, self.charge):
            self.say("FDC: INGEN NEDSLAGSRAPPORT ATT KORRIGERA MOT.", "bad")
            return
        ra, rc, ti = self.last
        st = self.m.targets[ti]
        v = CHARGES[self.charge]
        new_r = rng_for(v, self.elev) - ra
        e = elev_for(v, new_r)
        if e is None or not 5 <= e <= 85:
            self.say("FDC: KORREKTIONEN GAR INTE MED DENNA LADDNING.", "bad")
            return
        self.az = round((self.az - math.degrees(rc / st.dist)) % 360, 1)
        self.elev = round(e, 1)
        self.last = None
        self.say(f"FDC: KORREKTION MOT MAL {st.letter} KLAR. "
                 f"AZ {self.az:.1f}  EL {self.elev:.1f}", "hi")

    def fire(self):
        if self.state != "aim":
            self.say("INGET UPPDRAG PAGAR. TRYCK ENTER.", "bad")
            return
        if None in (self.az, self.elev, self.charge):
            self.say("FDC: SATT AZ, EL OCH LAD INNAN ELD.", "bad")
            return
        m = self.m
        if self.ammo_type is None:
            self.say("FDC: VALJ GRANAT (HE ELLER APHE) INNAN ELD.", "bad")
            return
        if m.stock[self.ammo_type] <= 0:
            self.say(f"SLUT PA {self.ammo_type}. VALJ ANNAN GRANAT.", "bad")
            return
        v = CHARGES[self.charge]
        R = rng_for(v, self.elev)
        T = tof(v, self.elev)
        m.stock[self.ammo_type] -= 1
        self.shot_type = self.ammo_type
        self.shot_target = self.sel
        opt = 0.85 ** self.p["optics"]
        Ra = R * (1 + random.gauss(0, 0.005 * opt))
        aza = math.radians(self.az + random.gauss(0, 0.12 * opt))
        wx, wy = m.wind_vec()
        self.pending = (GUN[0] + Ra * math.sin(aza) + 0.25 * wx * T,
                        GUN[1] + Ra * math.cos(aza) + 0.25 * wy * T)
        self.t_left = T
        self.shop_open = False
        self.state = "flight"
        self.say(f"ELD! {self.shot_type} MOT MAL {self.cur.letter}: LAD {self.charge} "
                 f"AZ {self.az:.1f} EL {self.elev:.1f} - NEDSLAG OM {T:.0f} S", "hi")

    def update(self, dt):
        if self.state == "flight":
            self.t_left -= dt * 8.0           # tidsforskjutning
            if self.t_left <= 0:
                self.impact()

    def impact(self):
        m = self.m
        typ = self.shot_type
        spec = AMMO_TYPES[typ]
        ix, iy = self.pending
        m.impacts.append((ix, iy))
        n = len(m.impacts)
        st = m.targets[self.shot_target]
        dx, dy = ix - st.x, iy - st.y
        ux = (st.x - GUN[0]) / st.dist
        uy = (st.y - GUN[1]) / st.dist
        along = dx * ux + dy * uy
        cross = dx * uy - dy * ux              # positivt = till hoger
        ra = int(round(along / 10.0)) * 10
        rc = int(round(cross / 10.0)) * 10
        off = describe(ra, rc)
        if self.spotter:
            self.last = (ra, rc, self.shot_target)

        if m.friend and math.hypot(ix - m.friend[0], iy - m.friend[1]) <= FRIEND_R:
            self.say("NEDSLAG! EGNA TRUPPER RAPPORTERAR ATT DE BLIVIT TRAFFADE!", "bad")
            self.report = "EGNA TRUPPER TRAFFADE!"
            self.trust -= 1
            self.points -= 100
            self.end_mission("EGNA TRUPPER TRAFFADES. UPPDRAGET AVBRUTET.", False)
            return

        # skada pa alla mal inom radien
        hits, destroyed = [], []
        for idx, t in enumerate(m.targets):
            if t.alive and math.hypot(ix - t.x, iy - t.y) <= spec["radius"]:
                dmg = spec["dmg"][t.hard]
                t.hp -= dmg
                hits.append((t, dmg))
                if t.hp <= 0:
                    t.hp = 0
                    destroyed.append(t)

        if self.spotter:
            self.report = f"NEDSLAG {n} ({typ}) MOT MAL {st.letter}: {off}"
            self.say(f"SPEJARE: NEDSLAG {off} (MOT MAL {st.letter}).", "fo")
            for t, dmg in hits:
                if t.alive:
                    self.say(f"  TRAFF MAL {t.letter} ({t.name}): {dmg}% SKADA, "
                             f"{t.hp}% KVAR.", "ok")
        else:
            self.report = f"NEDSLAG {n} ({typ}) EJ OBSERVERAT"
            self.say("NEDSLAG EJ OBSERVERAT - INGEN SPEJARE.", "n")

        who = "SPEJARE" if self.spotter else "SIGNALSPANING"
        for t in destroyed:
            pts = 100 + 10 * m.n
            self.points += pts
            self.say(f"{who}: MAL {t.letter} ({t.name}) UTSLAGET! +{pts} POANG", "ok")
        if destroyed:
            self.reselect()

        if all(not t.alive for t in m.targets):
            bonus = 50 + 40 * m.total_ammo()
            self.points += bonus
            self.p["won"] += 1
            self.say(f"ALLA MAL UTSLAGNA! BONUS +{bonus} POANG", "ok")
            self.end_mission("UPPDRAGET LYCKADES.", True)
        elif m.total_ammo() <= 0:
            left = sum(1 for t in m.targets if t.alive)
            self.say(f"SLUT PA GRANATER. {left} MAL OVERLEVDE.", "bad")
            self.trust -= 1
            self.end_mission("UPPDRAGET MISSLYCKADES.", False)
        else:
            self.say(f"GRANATER KVAR: {self.stock_text()}", "n")
            self.state = "aim"

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
    lines = []                       # (x-offset, text, attr)
    for item in items:
        if isinstance(item, tuple):
            cmd, desc = item
            wrapped = textwrap.wrap(desc, max(10, inner - 20)) or [""]
            for j, ln in enumerate(wrapped):
                if j == 0:
                    lines.append(("row", cmd, ln))   # kommando + forsta radens text
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
    YEL = curses.color_pair(3) | curses.A_BOLD
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
        mark = ">" if i == g.sel else " "
        if t.alive:
            stv = f"{t.hp}%" if g.spotter else "??"
            line = (f"{mark}{t.letter} {t.name:<16} {SKYDD_KORT[t.hard]:<6} "
                    f"O{t.x:04.0f} N{t.y:04.0f} {t.dist:4.0f}M AZ{t.bearing:5.1f} {stv}")
            pl(row, 1, line, RED if i == g.sel else RED_N)
        else:
            pl(row, 1, f"{mark}{t.letter} {t.name:<16} UTSLAGET", GREEN)
        row += 1
    pl(row, 1, f"VIND {m.wind} M/S FRAN {m.wfrom:03d} GRADER", G_B)
    row += 1
    if m.friend:
        pl(row, 1, f"EGNA TRUPPER: O{m.friend[0]:04.0f} N{m.friend[1]:04.0f}"
                   f"  EJ NARMARE AN {FRIEND_R:.0f} M", CYAN)
    else:
        pl(row, 1, "EGNA TRUPPER: INGA I OMRADET", GREEN)
    row += 1
    az = "--" if g.az is None else f"{g.az:.1f}"
    el = "--" if g.elev is None else f"{g.elev:.1f}"
    ch = "--" if g.charge is None else str(g.charge)
    am = "--" if g.ammo_type is None else g.ammo_type
    pl(row, 1, f"INSTALLT: MAL {g.cur.letter}  AZ {az}  EL {el}  LAD {ch}  GRAN {am}", YEL)
    row += 1
    sp = "SPEJARE: JA" if g.spotter else "SPEJARE: NEJ"
    pl(row, 1, f"{sp}  RAPPORT: {g.report}", CYAN)
    sep = row + 1
    put(scr, sep, 0, "-" * (panel_x - 2), GREEN)
    put(scr, sep, 2, " A-D mal  G kanon  F egna  siffror = nedslag (spejare) ", GREEN)

    # ---- karta ----
    mx0, my0 = 3, sep + 1
    mw = panel_x - 2 - mx0
    mh = (h - 7) - my0

    def cell(x, y):
        if not (0 <= x <= MAP_M and 0 <= y <= MAP_M):
            return None
        c = mx0 + int(x / MAP_M * (mw - 1) + 0.5)
        r = my0 + (mh - 1) - int(y / MAP_M * (mh - 1) + 0.5)
        return r, c

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
    if g.spotter:
        for t in m.targets:
            p = cell(t.x, t.y)
            if p:
                if t.alive:
                    put(scr, p[0], p[1], t.letter, RED)
                else:
                    put(scr, p[0], p[1], "x", GREEN)
        if m.friend:
            p = cell(*m.friend)
            if p:
                put(scr, p[0], p[1], "F", CYAN)
        for i, (ix, iy) in enumerate(m.impacts):
            p = cell(ix, iy)
            if p:
                put(scr, p[0], p[1], str((i + 1) % 10), YEL)

    # ---- skjuttabell + granattabell till hoger ----
    L = [("SKJUTTABELL (ELEVATION)", G_B),
         ("AVST    L1     L2     L3", GREEN)]
    for r in range(1500, 5501, 500):
        line = f"{r:4d}"
        for c in (1, 2, 3):
            e = elev_for(CHARGES[c], r)
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
        by = my0 + 1
        put(scr, by, bx, "+" + "-" * (bw - 2) + "+", G_B)
        head = f" BUTIK {'':<30}POANG {g.points}"
        put(scr, by + 1, bx, "|" + head.ljust(bw - 2)[:bw - 2] + "|", G_B)
        for i, (label, price) in enumerate(SHOP):
            status, ok = g.shop_status(i)
            line = f" {i + 1} {label:<33}{price:>5}  {status}"
            attr = G_B if (ok and g.points >= price) else GREEN
            put(scr, by + 2 + i, bx, "|" + line.ljust(bw - 2)[:bw - 2] + "|", attr)
        r0 = by + 2 + len(SHOP)
        put(scr, r0, bx, "|" + " ".ljust(bw - 2) + "|", GREEN)
        put(scr, r0 + 1, bx, "|" + " KOP <NR> = KOP     BUTIK = STANG".ljust(bw - 2) + "|", YEL)
        put(scr, r0 + 2, bx, "+" + "-" * (bw - 2) + "+", G_B)

    # ---- logg + kommandorad langst ner ----
    rows = g.log[-4:]
    for i, (text, kind) in enumerate(rows):
        put(scr, h - 6 + i, 0, text, kinds.get(kind, GREEN))
    put(scr, h - 2, 0, "-" * (w - 1), GREEN)
    if g.state == "flight":
        put(scr, h - 1, 0, f"GRANAT I LUFTEN...  NEDSLAG OM {max(0, g.t_left):.0f} S", YEL)
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
