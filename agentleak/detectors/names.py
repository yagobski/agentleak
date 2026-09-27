# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Full names in prose, without a keyword in front of them.

``patient Jean Tremblay`` was found; ``summary generated for Jean Tremblay``
was not, because the only person-name pattern needed a keyword. Prose recall
for names was 0 of 96 in ``docs/detection-quality.md``, and prose is how names
travel between agents: in a log line, an inter-agent message, a final answer.

This is a gazetteer, not a model: a common given name, followed by one or two
capitalised words. It is deterministic and cheap, and its limits are exactly
the list's: a name that is not in it is not found, and the list leans towards
names common in North America and France. Given names that are also ordinary
English words (Will, May, Grace, Mark…) are left out, because "Grace Period"
and "Mark Down" are not people.
"""

from __future__ import annotations

import re

__all__ = ["FULL_NAME_RE"]

_GIVEN_NAMES = """
aaron abigail adam adrian aidan alan albert alex alexander alexandra alexis alice
alicia alison allison alyssa amanda amber amelia amy ana andrea andrew angela
angelica anita ann anna anne annie anthony antoine antonio ashley audrey austin
barbara benjamin bernard beth bethany betty beverly blake bonnie bradley brandon
brenda brendan brian brianna bridget brittany brooke bruce bryan caitlin caleb
cameron camille carl carla carlos carmen carol caroline carolyn casey catherine
cathy cecilia chad charles charlotte chelsea cheryl chloe christian christina
christine christopher cindy claire clara claude claudia colin connie connor corey
courtney craig crystal cynthia dakota dale damien dan dana daniel danielle darius
darren david deborah debra denise dennis derek diana diane dominic donald donna
doris dorothy douglas dustin dylan edward eileen elaine eleanor elena elijah
elizabeth ellen emily emma eric erica erik erin ethan eugene evan evelyn fatima
felicia fernando fiona florence frances francesca francis francisco gabriel
gabrielle gail gary genevieve george gerald gina gloria gordon gregory hailey
hannah harold harry heather heidi helen henry holly howard hugo ian irene isaac
isabel isabella isabelle jacob jacqueline jake jamal james jamie jane janet janice
jared jasmine jason javier jean jeffrey jennifer jeremy jerome jesse jessica
jillian joan joanne joel john jonathan jordan jorge jose joseph joshua joyce juan
judith judy julia julian julie justin kaitlyn karen karim katherine kathleen kathryn
kathy katie kayla keith kelly kenneth kevin kimberly kristen kristin kyle kylie
laura lauren laurie lawrence leah leonard leslie liam linda lindsay lisa logan
lori louis louise lucas lucy luis luke lydia lynn madeleine madison manon marc
marcus margaret maria mariam marie marilyn mario marion marissa martha martin
mary mathieu matthew maxime megan melanie melissa michael michel michelle miguel
mohamed mohammed monica morgan nadia nancy natalie nathalie nathan nicholas nicole
noah noel olivia olivier omar pamela patricia patrick paul paula pedro peter
philip philippe pierre priya rachel rafael rahul ralph randy raymond rebecca regina
renee ricardo richard robert roberto robin rodney roger ronald rosa russell ruth
ryan samantha samuel sandra sara sarah scott sean sebastien sergio shannon sharon
shawn sheila shirley simon sofia sophia sophie stacy stephanie stephen steven susan
sylvie tamara tammy tanya teresa thomas tiffany timothy tina todd tommy tony tracy
travis tyler valerie vanessa veronica victor victoria vincent virginia walter wanda
wayne wendy william xavier yasmine yolanda yves zachary zoe
chantal francois françois genevieve geneviève guillaume helene hélène jacques josee
josée julien louise lucie marc-andre marc-andré mathilde melanie mélanie nicolas
pascal stephane stéphane therese thérèse valerie valérie veronique véronique
emilie émilie etienne étienne francine gilles ginette jocelyne lise luc maude remi
rémi rejean réjean sebastien sébastien solange yannick
"""

# Stored lowercase so that this file, scanned by `agentleak scan`, does not read
# as a list of people; str.title() restores "Marc-André" and "Émilie".
_GIVEN = sorted({name.title() for name in _GIVEN_NAMES.split() if name}, key=len, reverse=True)

# A surname: capitalised, letters with an inner apostrophe or hyphen allowed
# (O'Brien, Saint-Laurent). Lowercase particles are not followed, so
# "Jean de la Fontaine" is found as "Jean", which the pattern then rejects —
# a miss, stated rather than guessed at.
_SURNAME = r"[A-ZÀ-Ý][a-zà-ÿ]+(?:['’-][A-ZÀ-Ý]?[a-zà-ÿ]+)?"

# Words that follow a given name and make it a place, a product or a heading,
# not a person: "Jordan River", "Victoria Street", "Adam Optimizer".
_NOT_SURNAMES = frozenset("""
Street Avenue Road Boulevard Drive Lane Court Place Square Park River Lake Bay
Hotel Hospital University College School Station Airport Bridge County City
Center Centre Group Inc Corp Ltd Company Foundation Institute Optimizer Protocol
Test Tests Case Cases Mode Model Street Day Week Month Year Monday Tuesday
Wednesday Thursday Friday Saturday Sunday January February March April June July
August September October November December The And Or Of For With From Is Are Was
Suite Ste Apt Apartment Unit Floor Building
""".split()) | frozenset(
    # Street-type words: "Amanda Manors", "Andrea Trail" and "Amber Crescent" are
    # streets named after people, and the address detector owns them.
    """Street St Avenue Ave Road Rd Boulevard Blvd Drive Dr Lane Ln Court Ct Way Place Pl
    Circle Crescent Terrace Parkway Highway Square Squares Trail Park Pike Plaza Point
    Ridge Row Run Spur Station Pines Manor Manors Mews Loop Locks Lock Landing Knoll
    Knolls Junction Heights Harbor Grove Green Gardens Garden Freeway Estates Crossing
    Crossroad Crossroads Cove Creek Bridge Bypass Branch Bend Alley Villages Village
    Views View Valley Turnpike Summit Springs Spring Shores Shore Port Prairie Pass Oval
    Orchard Mill Mills Meadows Meadow Lodge Island Isle Hollow Hills Hill Glen Gateway
    Forest Fork Forks Fields Field Falls Expressway Dale Courts Corners Corner Common
    Commons Cliffs Causeway Canyon Burg Brooks Brook Bluffs Bluff Beach Walk Walks
    Ville Extension Extensions Mountain Mountains Camp Ramp Ranch Keys Key Lakes Forge
    Forges Ports Radial Skyway Stravenue Throughway Tunnel Underpass Viaduct Vista""".split()
)

FULL_NAME_RE = re.compile(
    r"(?<![\w@.-])(" + "|".join(re.escape(n) for n in _GIVEN) + r")"
    r"(?:[ \t]+(" + _SURNAME + r")){1,2}(?![\w@])"
)


def full_names(text: str) -> list[str]:
    """Full names in *text*: a known given name and one or two surnames."""
    found: list[str] = []
    for m in FULL_NAME_RE.finditer(text):
        # A possessive is the name plus grammar: "Alex Green's file" is Alex Green.
        words = [re.sub(r"['’]s$", "", word) for word in m.group(0).split()]
        while len(words) > 1 and words[-1] in _NOT_SURNAMES:
            words.pop()
        if len(words) < 2 or any(word in _NOT_SURNAMES for word in words[1:]):
            continue
        found.append(" ".join(words))
    return found
