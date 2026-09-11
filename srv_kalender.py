#!/usr/bin/env python3
"""Hämtar SRV Återvinnings hämtningsdatum för en adress och skriver en .ics-kalender.

Användning:
    SRV_ADRESS="Storgatan 1" SRV_ORT="ORTNAMN" python3 srv_kalender.py sophamtning.ics

SRV_ORT (postort) är valfri men gör sökningen säkrare om gatunamnet finns på flera orter.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

# Samma (inofficiella) API som SRV:s webbsida använder.
API = "https://www.srvatervinning.se/rest-api/core/sewagePickup/search"


def hamta(adress, ort):
    params = urllib.parse.urlencode({"query": adress, "city": ort.upper()})
    req = urllib.request.Request(
        f"{API}?{params}",
        headers={"User-Agent": "Mozilla/5.0 (srv-kalender)", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as svar:
        return json.load(svar)


def samla(data):
    """Returnerar {datum: {avfallstyp, ...}}. Avbryter hellre än att skriva en tom kalender."""
    resultat = data.get("results") or []
    if not resultat:
        sys.exit("Hittade ingen adress. Kontrollera SRV_ADRESS och SRV_ORT.")
    if len(resultat) > 1:
        print(f"Obs: {len(resultat)} adresser matchade, använder den första. Ange SRV_ORT för säkerhets skull.")

    hamtningar = {}
    for karl in resultat[0].get("containers", []):
        typ = (karl.get("contentType") or "Avfall").strip()
        for post in karl.get("calendars", []):
            dag = date.fromisoformat(post["startDate"][:10])
            hamtningar.setdefault(dag, set()).add(typ)

    if not hamtningar:
        sys.exit("Inga hämtningsdatum hittades. Den gamla kalendern lämnas orörd.")
    return hamtningar


def esc(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(rad):
    """Kalenderformatet tillåter max 75 byte per rad; längre rader bryts."""
    delar, aktuell = [], ""
    for tecken in rad:
        if len((aktuell + tecken).encode("utf-8")) > 75:
            delar.append(aktuell)
            aktuell = " " + tecken
        else:
            aktuell += tecken
    delar.append(aktuell)
    return "\r\n".join(delar)


def bygg_ics(hamtningar):
    rader = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//srv-kalender//SV",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Sophämtning",
        "X-WR-TIMEZONE:Europe/Stockholm",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for dag in sorted(hamtningar):
        typer = ", ".join(sorted(hamtningar[dag]))
        rader += [
            "BEGIN:VEVENT",
            f"UID:{dag:%Y%m%d}@srv-kalender",
            # Fast tidsstämpel så att filen bara ändras när datumen ändras.
            f"DTSTAMP:{dag:%Y%m%d}T000000Z",
            f"DTSTART;VALUE=DATE:{dag:%Y%m%d}",
            f"DTEND;VALUE=DATE:{dag + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + esc(f"Sophämtning: {typer}"),
            "DESCRIPTION:" + esc("Hämtning sker mellan kl. 06 och 15. Ställ ut kärlen kvällen innan."),
            "TRANSP:TRANSPARENT",
            # Påminnelse kl. 19 kvällen före (5 timmar före midnatt).
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:" + esc(f"Ställ ut kärlen: {typer}"),
            "TRIGGER:-PT5H",
            "END:VALARM",
            "END:VEVENT",
        ]
    rader.append("END:VCALENDAR")
    return "\r\n".join(fold(r) for r in rader) + "\r\n"


def main():
    adress = os.environ.get("SRV_ADRESS", "").strip()
    ort = os.environ.get("SRV_ORT", "").strip()
    utfil = sys.argv[1] if len(sys.argv) > 1 else "sophamtning.ics"
    if not adress:
        sys.exit('Ange adressen i SRV_ADRESS, t.ex. SRV_ADRESS="Storgatan 1".')

    hamtningar = samla(hamta(adress, ort))
    with open(utfil, "w", encoding="utf-8", newline="") as f:
        f.write(bygg_ics(hamtningar))
    # Skriver medvetet inte ut adressen, eftersom loggarna syns publikt på GitHub.
    print(f"Klart: {len(hamtningar)} hämtningsdagar skrivna till {utfil}.")


if __name__ == "__main__":
    main()
