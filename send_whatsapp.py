#!/usr/bin/env python3
"""Envoie un message WhatsApp via CallMeBot.

Usage : python3 send_whatsapp.py message.txt
Variables d'env requises : CALLMEBOT_PHONE, CALLMEBOT_APIKEY
Si le message dépasse MAX_CHARS, il est découpé proprement sur les séparateurs
entre offres (ligne "──────") et envoyé en plusieurs parties.
"""
import os
import sys
import time
import urllib.parse
import urllib.request

MAX_CHARS = 3000
SEP = "──────────────────────"


def chunks(text: str):
    if len(text) <= MAX_CHARS:
        return [text]
    blocks = text.split(SEP)
    out, cur = [], ""
    for i, b in enumerate(blocks):
        piece = b if i == 0 else SEP + b
        if cur and len(cur) + len(piece) > MAX_CHARS:
            out.append(cur.strip())
            cur = b.lstrip("\n")  # nouvelle partie : pas de séparateur en tête
        else:
            cur += piece
    if cur.strip():
        out.append(cur.strip())
    return out


def send(phone: str, apikey: str, text: str) -> str:
    qs = urllib.parse.urlencode({"phone": phone, "apikey": apikey, "text": text})
    url = "https://api.callmebot.com/whatsapp.php?" + qs
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def main():
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    text = open(sys.argv[1], encoding="utf-8").read().strip()
    parts = chunks(text)
    ok = True
    for n, part in enumerate(parts, 1):
        if len(parts) > 1:
            part = f"({n}/{len(parts)})\n" + part
        resp = send(phone, apikey, part)
        low = resp.lower()
        if "error" in low or "paused" in low or "invalid" in low:
            ok = False
            print(f"ECHEC partie {n}: {resp[:500]}")
        else:
            print(f"OK partie {n}/{len(parts)} ({len(part)} caractères)")
        if n < len(parts):
            time.sleep(12)  # CallMeBot limite le débit
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
