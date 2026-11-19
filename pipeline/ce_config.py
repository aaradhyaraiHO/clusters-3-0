"""Per-CE vocabulary for the head-term rule and the mapper guard.

NAME tokens: words that only name the attraction (any language); they carry no intent.
HEAD / TICKETS: the clusters that name-only and name + ticket-word searches belong to (both live on the landing page).
"""
STOP = {"the", "and", "for", "with", "from", "how", "what", "can", "you", "are", "does", "near", "in", "of", "to", "a",
        "de", "del", "la", "le", "les", "el", "di", "il", "das", "der", "die", "na", "do", "du", "et", "y", "e", "und", "per", "pour", "para"}
CITY = {"rome", "roma", "rom", "rzym", "barcelona", "barcelone", "barcellona", "barcelone", "city", "citta", "stadt", "spain", "italy"}
TICKET = {"ticket", "tickets", "biglietti", "biglietto", "entradas", "entrada", "billet", "billets", "eintritt", "eintrittskarten",
          "eintrittskarte", "karten", "bilety", "bilet", "bilete", "ingressos", "ingresso", "boletos", "entree", "jegyek", "liput",
          "admission", "entry", "booking", "book", "buy", "online", "kaufen", "comprar", "acheter", "prenotare", "reservar"}

TOUR = {"tour", "tours", "fuhrung", "fuhrungen", "visita guidata", "visite guidee", "excursion", "excursiones", "wycieczka", "rondleiding"}

# Translations and spellings that mean the same word: compared on the canonical form in the mapper guard
EQUIV_GROUPS = {
    "ticket": TICKET,
    "official": {"official", "oficial", "officiel", "officielle", "ufficiale", "ufficiali", "offiziell", "offizielle", "oficjalna",
                 "site", "sito", "sitio", "website", "web", "pagina", "strona", "seite"},
    "chapel": {"chapel", "cappella", "capilla", "capela", "chapelle", "kapel", "kapelle", "kaplica", "kapellet", "kapolna"},
    "sistine": {"sistine", "sistina", "sixtine", "sixtina", "sixtijnse", "sixtinische", "sykstynska", "sixtus", "sixteenth"},
    "visit": {"visit", "visita", "visite", "visitar", "besuch", "besichtigung", "zwiedzanie", "bezoek"},
    "tour": TOUR,
    "garden": {"garden", "gardens", "giardini", "jardines", "jardins", "garten", "ogrody", "tuinen"},
    "hours": {"hours", "horario", "horarios", "orari", "horaires", "offnungszeiten", "opening", "timings"},
}
CANON = {w: g for g, ws in EQUIV_GROUPS.items() for w in ws}

CE = {
    "189": {
        "name": {"vatican", "vaticano", "vatikan", "vaticaan", "watykan", "vatikanet", "vatikanen", "vaticani", "vaticana", "vaticanos",
                 "vatikanische", "vatikanischen", "watykanskie", "museum", "museums", "musei", "museo", "museos", "museu", "museus",
                 "museen", "muzea", "muzeum", "musee", "musees", "museivaticani", "va"},
        "head": "Vatican Museums (Musei Vaticani) - Head Term",
        "tickets": "Vatican Museums Tickets & Entry",
        "tours": "Guided Tours (Vatican Museums)",
    },
    "325": {
        "name": {"park", "parc", "parque", "parco", "parkguell", "guell", "guel", "gell", "gaudi"},
        "head": "Park Güell",
        "tickets": "Tickets & Prices",
        "tours": "Guided Tours",
    },
}


def generic(ce):
    """Words that say nothing about which cluster a search belongs to."""
    return STOP | CITY | CE[ce]["name"]
