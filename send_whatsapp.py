#!/usr/bin/env python3
"""Envoie un message WhatsApp via CallMeBot.

Usage : python3 send_whatsapp.py message.txt
Variables d'env requises : CALLMEBOT_PHONE, CALLMEBOT_APIKEY
CallMeBot TRONQUE silencieusement au-delà d'environ 740 caractères (testé le
7 novembre 2026). Le message est donc découpé sur les lignes séparatrices
(━━━ / ───) : en-tête, une offre par message, pied. Les morceaux trop longs
sont recoupés ligne par ligne ; les petits morceaux voisins sont regroupés.
"""
import os
import re
import sys
import time
import urllib.parse
import urllib.request

MAX_CHARS = 650  # marge sous la limite CallMeBot (~740)
SEP_RE = re.compile(r"^\s*[━─]{5,}\s*$")
JOIN = "\n──────────────────────\n"


def _split_long(seg: str):
    out, cur = [], ""
    for line in seg.split("\n"):
        while len(line) > MAX_CHARS:  # ligne énorme : coupe brute
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:MAX_CHARS])
            line = line[MAX_CHARS:]
        cand = f"{cur}\n{line}" if cur else line
        if len(cand) > MAX_CHARS:
            out.append(cur)
            cur = line
        else:
            cur = cand
    if cur.strip():
        out.append(cur)
    return out


def chunks(text: str):
    segs, cur = [], []
    for line in text.split("\n"):
        if SEP_RE.match(line):
            if "\n".join(cur).strip():
                segs.append("\n".join(cur).strip())
            cur = []
        else:
            cur.append(line)
    if "\n".join(cur).strip():
        segs.append("\n".join(cur).strip())
    pieces = []
    for s in segs:
        pieces.extend(_split_long(s) if len(s) > MAX_CHARS else [s])
    merged = []
    for p in pieces:
        if merged and len(merged[-1]) + len(JOIN) + len(p) <= MAX_CHARS:
            merged[-1] = merged[-1] + JOIN + p
        else:
            merged.append(p)
    return merged


def send(phone: str, apikey: str, text: str) -> str:
    qs = urllib.parse.urlencode({"phone": phone, "apikey": apikey, "text": text})
    url = "https://api.callmebot.com/whatsapp.php?" + qs
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def send_whatsapp_parts(parts, start: int = 0):
    """Envoie parts[start:]. Renvoie (ok, raison, index du premier morceau non envoyé)."""
    if os.environ.get("SIMULATE_WHATSAPP_FAIL"):  # test du plan B Telegram
        print("SIMULATION : échec WhatsApp forcé")
        return False, "simulation d’échec", start
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    for n in range(start, len(parts)):
        part = parts[n]
        try:
            resp = send(phone, apikey, part)
        except Exception as e:  # réseau, timeout…
            resp = f"error: {e}"
        low = resp.lower()
        if "error" in low or "paused" in low or "invalid" in low:
            reason = "compte en pause" if "paused" in low else resp[:200]
            print(f"ECHEC WhatsApp partie {n + 1}: {resp[:500]}")
            return False, reason, n
        print(f"OK WhatsApp partie {n + 1} sur {len(parts)} ({len(part)} caractères)")
        if n < len(parts) - 1:
            time.sleep(8)  # CallMeBot limite le débit ; garde l’ordre des messages
    return True, "", len(parts)


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("ECHEC Telegram : TELEGRAM_TOKEN / TELEGRAM_CHAT_ID absents")
        return False
    ok = True
    # Telegram : 4096 caractères max par message, texte brut
    pieces = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for p in pieces:
        # D'abord en Markdown (rend *gras* et _italique_ comme WhatsApp),
        # puis en texte brut si Telegram refuse (ex. « _ » dans une URL).
        for mode in ("Markdown", None):
            fields = {"chat_id": chat_id, "text": p, "disable_web_page_preview": "true"}
            if mode:
                fields["parse_mode"] = mode
            data = urllib.parse.urlencode(fields).encode()
            try:
                with urllib.request.urlopen(
                    f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=60
                ) as r:
                    resp = r.read().decode("utf-8", "replace")
            except Exception as e:
                resp = f"error: {e}"
            if '"ok":true' in resp:
                break
        if '"ok":true' not in resp:
            ok = False
            print(f"ECHEC Telegram : {resp[:300]}")
    if ok:
        print("OK Telegram (plan B)")
    return ok


def main():
    text = open(sys.argv[1], encoding="utf-8").read().strip()
    text = text.replace("'", "’")  # CallMeBot supprime les apostrophes droites
    parts = chunks(text)
    ok, reason, nxt = send_whatsapp_parts(parts)
    if not ok:
        time.sleep(30)
        print("Nouvel essai WhatsApp (à partir du morceau en échec)…")
        ok, reason, nxt = send_whatsapp_parts(parts, nxt)
    if ok:
        sys.exit(0)
    rest = JOIN.join(parts[nxt:])
    alert = (
        f"⚠️ WhatsApp en échec ({reason}) : {nxt} message(s) sur {len(parts)} envoyés.\n"
        "Si le compte est en pause : envoie « resume » au +34 644 91 07 79 sur WhatsApp.\n"
        "Suite du scan ci-dessous.\n\n"
    )
    sys.exit(0 if send_telegram(alert + rest) else 1)


if __name__ == "__main__":
    main()
