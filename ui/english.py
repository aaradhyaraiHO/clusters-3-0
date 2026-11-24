"""English-only scope for clusters, keywords, search terms and Perf data (user's rule, 24 Nov 2026).

Decided by the language of the text, not of the campaign:
1. Keywords and clusters: English only (the EOS clusters prompt already drops non-English keywords that are not proper
   names; is_english() checks the result again).
2. Search terms: English only, whichever campaign served them. An English search in the Spanish campaign is English
   demand Headout already pays for, so it counts; a Spanish search in the English campaign does not.
3. Keyword-level data (bid status, Quality Score, keyword totals): English keywords, in any campaign.
4. Organic: only English pages, i.e. URLs without a language folder (/it/, /es/, /pt-br/ ...).
"""
import re
import unicodedata

# Words that only appear in non-English searches for these CEs: ticket, opening-hours, price, booking, getting-there
# and place words in Spanish, Italian, German, French, Portuguese, Dutch, Polish, Romanian, Turkish and the Nordic
# languages. Words that are also English or common in English queries ("come", "dove", "per", "sin", "la", "nova",
# "program", "zeeland" as a misspelling of Zealand) are left out on purpose: a false drop loses an English search.
FOREIGN = set("""
entradas entrada boletos boleto billetes museos museo capilla sixtina horario horarios precio precios guiada guiadas
llegar cuanto cuesta donde comprar reservar desde para colas oficial sitio pagina crucero cruceros mejor que hacer
nueva zelanda vaticano vaticanos visitar
biglietti biglietto musei vaticani cappella sistina orari orario prezzo prezzi guidata guidate prenotazione prenotare
ingresso gratuito arrivare ufficiale salta fila della dei degli delle crociera crociere nuova
eintrittskarten eintrittskarte karten museen vatikanische vatikanischen vatikan sixtinische kapelle offnungszeiten
preise preis fuhrung fuhrungen eintritt kostenlos anfahrt buchen ohne anstehen bootsfahrt bootstour bootstouren schifffahrt
kreuzfahrt neuseeland und nach
billets billet musees musee chapelle sixtine horaires tarif tarifs prix visite guidee reserver gratuit comment aller
croisiere croisieres nouvelle zelande des du
ingressos bilhetes museus capela horarios preco passeio passeios cruzeiro cruzeiros chegar zelandia
kaartjes kaarten musea kapel sixtijnse openingstijden prijzen prijs rondleiding bezoeken nieuw boottocht toegang ingang vaticaans het
bilety biletow muzea muzeum kaplica sykstynska godziny otwarcia cena ceny zwiedzanie watykan watykanskie nowa zelandia rejs
bilete muzeele muzeul capela pret
muzesi bilet giris fiyat fiyatlari
biljetter billetter museer kapell kapellet oppettider abningstider pris vatikanet vatikanen vatikanstaten sixtinske sixtinska
vaticaan vaticaanstad vaticaanse muzeu
""".split())
LANG_FOLDER = re.compile(r"^[a-z]{2}(?:-[a-z]{2,4})?$")


def fold(text):
    """Lower case without accents: 'Öffnungszeiten' -> 'offnungszeiten'."""
    return unicodedata.normalize("NFKD", str(text).lower()).encode("ascii", "ignore").decode()


def words(text):
    return re.findall(r"[^\W\d_]+", str(text).lower())


def english_checker(proper_names):
    """is_english(term) for one CE. proper_names (the CE's and its clusters' names) keep accented proper nouns such as
    Güell or Família, and named places such as Vaticano in a cluster name, from counting as foreign."""
    # A bracketed part of a cluster name is often the local-language alias ("Vatican Museums (Musei Vaticani)"); it
    # must not make that alias count as English.
    bare = [re.sub(r"\(.*?\)", " ", str(name)) for name in proper_names]
    allowed = {w for name in bare for w in words(name)} | {fold(w) for name in bare for w in words(name)}

    def is_english(term):
        for word in words(term):
            if word in allowed:
                continue
            if not word.isascii():
                # Another script (Cyrillic, Greek, CJK ...) or an accented Latin word that is not one of the CE's names.
                return False
            if word in FOREIGN:
                return False
        return True

    return is_english


def english_page(url):
    path = re.sub(r"^https?://[^/]+", "", str(url or "")).strip("/")
    first = path.split("/")[0].lower() if path else ""
    return not (LANG_FOLDER.match(first) and first != "en")
