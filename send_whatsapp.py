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


def send_whatsapp_all(text: str) -> tuple[bool, str]:
    phone = os.environ["CALLMEBOT_PHONE"]
    apikey = os.environ["CALLMEBOT_APIKEY"]
    parts = chunks(text)
    for n, part in enumerate(parts, 1):
        if len(parts) > 1:
            part = f"Partie {n} sur {len(parts)}\n" + part  # pas de "1/2" : WhatsApp le souligne
        try:
            resp = send(phone, apikey, part)
        except Exception as e:  # réseau, timeout…
            resp = f"error: {e}"
        low = resp.lower()
        if "error" in low or "paused" in low or "invalid" in low:
            reason = "compte en pause" if "paused" in low else resp[:200]
            print(f"ECHEC WhatsApp partie {n}: {resp[:500]}")
            return False, reason
        print(f"OK WhatsApp partie {n}/{len(parts)} ({len(part)} caractères)")
        if n < len(parts):
            time.sleep(12)  # CallMeBot limite le débit
    return True, ""


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
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": p, "disable_web_page_preview": "true",
        }).encode()
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=60
            ) as r:
                resp = r.read().decode("utf-8", "replace")
        except Exception as e:
            resp = f"error: {e}"
        if '"ok":true' not in resp:
            ok = False
            print(f"ECHEC Telegram : {resp[:300]}")
    if ok:
        print("OK Telegram (plan B)")
    return ok


def main():
    text = open(sys.argv[1], encoding="utf-8").read().strip()
    text = text.replace("'", "’")  # CallMeBot supprime les apostrophes droites
    ok, reason = send_whatsapp_all(text)
    if not ok:
        time.sleep(30)
        print("Nouvel essai WhatsApp…")
        ok, reason = send_whatsapp_all(text)
    if ok:
        sys.exit(0)
    alert = (
        f"⚠️ WhatsApp en échec ({reason}).\n"
        "Si le compte est en pause : envoie « resume » au +34 644 91 07 79 sur WhatsApp.\n\n"
    )
    sys.exit(0 if send_telegram(alert + text) else 1)


if __name__ == "__main__":
    main()
