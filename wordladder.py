#!/usr/bin/env python3
import argparse
import heapq
import json
import os
import re
import sys
import urllib.request
from collections import deque

try:
    import curses
except ImportError:
    curses = None

bdir = os.path.dirname(os.path.abspath(__file__))

srcs = {
    "scowl": {
        "url": "https://raw.githubusercontent.com/en-wl/wordlist/v2/data/scowl-pre.txt",
        "cache": os.path.join(bdir, "words_scowl.txt"),
        "ranked": True,
    },
    "array": {
        "url": "https://raw.githubusercontent.com/words/an-array-of-english-words/master/index.json",
        "cache": os.path.join(bdir, "words_array.json"),
        "ranked": False,
    },
}

ecsh = os.path.join(bdir, "excluded.txt")

rtag = re.compile(r"<[^>]*>")


def ensr(srce):
    pcfg = srcs[srce]
    if not os.path.exists(pcfg["cache"]):
        sys.stderr.write(f"downloading {srce} word list to {pcfg['cache']} ...\n")
        urllib.request.urlretrieve(pcfg["url"], pcfg["cache"])
    return pcfg["cache"]


def pscl(path):
    rnks = {}
    with open(path, encoding="utf-8", errors="ignore") as fobj:
        for line in fobj:
            head, sepr, rest = line.partition(":")
            if not sepr:
                continue
            levs = [int(tval) for tval in head.split() if tval.isdigit()]
            levl = min(levs) if levs else 95
            for segm in rest.split(":"):
                for tokn in rtag.sub(" ", segm).split():
                    word = tokn.strip("~!?*-.+,'")
                    if word.isalpha() and word.islower() and levl < rnks.get(word, 1000):
                        rnks[word] = levl
    return rnks


def rdln(path):
    wrds = set()
    with open(path, encoding="utf-8", errors="ignore") as fobj:
        for line in fobj:
            prts = line.split()
            if prts and prts[0].isalpha():
                wrds.add(prts[0].lower())
    return wrds


def load(srce=None, path=None, comm=True):
    if path:
        if not os.path.exists(path):
            sys.exit(f"dictionary not found: {path}")
        return rdln(path), None

    cche = ensr(srce)
    if srce == "scowl":
        rnks = pscl(cche)
        return set(rnks), (rnks if comm else None)

    with open(cche, encoding="utf-8", errors="ignore") as fobj:
        wrds = {witm.lower() for witm in json.load(fobj) if witm.isalpha()}
    return wrds, None


def lexc():
    if not os.path.exists(ecsh):
        return set()
    with open(ecsh, encoding="utf-8", errors="ignore") as fobj:
        return {witm.strip().lower() for witm in fobj if witm.strip()}


def aexc(word):
    with open(ecsh, "a", encoding="utf-8") as fobj:
        fobj.write(word + "\n")


def nbrs(word, wrds):
    lets = "abcdefghijklmnopqrstuvwxyz"

    for indx in range(len(word)):
        for chrc in lets:
            if chrc != word[indx]:
                cand = word[:indx] + chrc + word[indx + 1:]
                if cand in wrds:
                    yield cand

    for indx in range(len(word) + 1):
        for chrc in lets:
            cand = word[:indx] + chrc + word[indx:]
            if cand in wrds:
                yield cand

    for indx in range(len(word)):
        cand = word[:indx] + word[indx + 1:]
        if cand in wrds:
            yield cand


def rcon(prev, endw):
    path = [endw]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path[::-1]


def ladr(strt, endw, wrds, rnks=None):
    strt, endw = strt.lower(), endw.lower()
    if strt not in wrds:
        sys.exit(f"start word not in dictionary: {strt}")
    if endw not in wrds:
        sys.exit(f"end word not in dictionary: {endw}")
    if strt == endw:
        return [strt]

    if rnks is None:
        prev = {strt: None}
        queu = deque([strt])
        while queu:
            word = queu.popleft()
            for nxtw in nbrs(word, wrds):
                if nxtw not in prev:
                    prev[nxtw] = word
                    if nxtw == endw:
                        return rcon(prev, endw)
                    queu.append(nxtw)
        return None

    rare = max(rnks.values()) + 1
    def levf(wval):
        return rnks.get(wval, rare)

    prev = {strt: None}
    best = {strt: (0, levf(strt))}
    pque = [(0, levf(strt), strt)]
    while pque:
        dpth, cost, word = heapq.heappop(pque)
        if (dpth, cost) > best[word]:
            continue
        if word == endw:
            return rcon(prev, endw)
        for nxtw in nbrs(word, wrds):
            cand = (dpth + 1, cost + levf(nxtw))
            if cand < best.get(nxtw, (sys.maxsize,)):
                best[nxtw] = cand
                prev[nxtw] = word
                heapq.heappush(pque, (cand[0], cand[1], nxtw))
    return None


class Sess:
    def __init__(self, strt, endw, wrds, rnks, excl):
        self.strt = strt
        self.endw = endw
        self.wrds = wrds
        self.rnks = rnks
        self.excl = excl
        self.scur = 0
        self.adds = []
        self.msge = ""
        self.recp()

    def recp(self):
        self.path = ladr(self.strt, self.endw, self.wrds, self.rnks)
        self.scur = min(self.scur, len(self.path) - 1) if self.path else 0

    def move(self, dlta):
        if self.path:
            self.scur = (self.scur + dlta) % len(self.path)

    def xsel(self):
        if not self.path:
            return
        word = self.path[self.scur]
        if word == self.strt or word == self.endw:
            self.msge = f"can't exclude the {'start' if word == self.strt else 'end'} word"
            return
        if word not in self.excl:
            aexc(word)
            self.excl.add(word)
            self.adds.append(word)
        self.wrds.discard(word)
        self.msge = f"excluded {word!r}"
        self.recp()


def sast(scrn, ypos, xpos, text, attr=0):
    try:
        scrn.addstr(ypos, xpos, text, attr)
    except curses.error:
        pass


def dldr(scrn, path, scur, ytop, wdth):
    ypos, xpos = ytop, 0
    for indx, word in enumerate(path):
        if xpos and xpos + len(word) > wdth:
            ypos, xpos = ypos + 1, 0
        attr = curses.A_REVERSE if indx == scur else curses.A_NORMAL
        sast(scrn, ypos, xpos, word, attr)
        xpos += len(word)
        if indx != len(path) - 1:
            seps = " -> "
            if xpos + len(seps) > wdth:
                ypos, xpos = ypos + 1, 0
            else:
                sast(scrn, ypos, xpos, seps)
                xpos += len(seps)


def uifn(scrn, sess):
    curses.curs_set(0)
    scrn.keypad(True)
    while True:
        scrn.erase()
        hght, wdth = scrn.getmaxyx()
        sast(scrn, 0, 0,
             f"Word ladder: {sess.strt} -> {sess.endw}", curses.A_BOLD)
        if sess.path is None:
            sast(scrn, 2, 0, "no ladder found with the current exclusions")
        else:
            dldr(scrn, sess.path, sess.scur, 2, wdth)
        hlpl = "move: <- ->   exclude word: x   quit: q"
        sast(scrn, max(0, hght - 2), 0, sess.msge or hlpl)
        sast(scrn, max(0, hght - 1), 0,
             f"{len(sess.excl)} word(s) excluded in total")
        scrn.refresh()
        sess.msge = ""

        chrc = scrn.getch()
        if chrc in (ord("q"), 27):
            break
        elif chrc in (curses.KEY_LEFT, ord("h")):
            sess.move(-1)
        elif chrc in (curses.KEY_RIGHT, ord("l")):
            sess.move(1)
        elif chrc in (ord("x"), ord(" "), 10, 13, curses.KEY_ENTER):
            sess.xsel()


def pres(strt, endw, path):
    if path is None:
        print(f"no ladder found between {strt!r} and {endw!r}")
    else:
        print(" -> ".join(path))
        print(f"({len(path)} words, {len(path) - 1} steps)")


def rint(strt, endw, wrds, rnks, excl):
    sess = Sess(strt, endw, wrds, rnks, excl)
    curses.wrapper(uifn, sess)
    pres(strt, endw, sess.path)
    if sess.adds:
        print(f"excluded this session: {', '.join(sess.adds)}")


def main():
    apar = argparse.ArgumentParser(description="Minimum-length word ladder.")
    apar.add_argument("start")
    apar.add_argument("end")
    apar.add_argument("--array", action="store_true",
                      help="use the an-array-of-english-words list (~275k, no commonness data)")
    apar.add_argument("--dict", dest="dpth", help="path to your own word list")
    apar.add_argument("--common", action=argparse.BooleanOptionalAction, default=True,
                      help="prefer common words among shortest ladders "
                           "(default; --no-common returns any shortest ladder)")
    apar.add_argument("--plain", action="store_true",
                      help="non-interactive: print one ladder and exit")
    args = apar.parse_args()

    srce = "array" if args.array else "scowl"
    wrds, rnks = load(srce=None if args.dpth else srce,
                      path=args.dpth, comm=args.common)
    if args.common and rnks is None and not args.dpth:
        sys.stderr.write(f"note: the {srce} list has no commonness data; "
                         "returning an arbitrary shortest ladder\n")

    strt, endw = args.start.lower(), args.end.lower()

    excl = lexc()
    wrds -= excl - {strt, endw}
    if excl:
        sys.stderr.write(f"({len(excl)} excluded word(s) loaded from {ecsh})\n")

    if strt not in wrds:
        sys.exit(f"start word not in dictionary: {strt}")
    if endw not in wrds:
        sys.exit(f"end word not in dictionary: {endw}")

    intr = (not args.plain and curses is not None
            and sys.stdin.isatty() and sys.stdout.isatty())
    if intr:
        rint(strt, endw, wrds, rnks, excl)
    else:
        pres(strt, endw, ladr(strt, endw, wrds, rnks))


if __name__ == "__main__":
    main()
