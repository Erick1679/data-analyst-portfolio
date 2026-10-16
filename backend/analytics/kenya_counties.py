"""Official Kenyan county number for display and ordering.

These 001–047 codes are Kenya's county numbers, not ISO 3166-2 codes.
Keep imported ISO identifiers (e.g. KE-01 for Baringo) and existing record
keys unchanged to preserve parent/indicator relations and provenance.

References:
https://gok.kenya.go.ke/devolved-governments
https://new.kenyalaw.org/akn/ke/officialGazette/gazette/2024-05-09/64/eng@2024-05-09/source
"""
import re
import unicodedata

COUNTIES_IN_OFFICIAL_ORDER = (
    "Mombasa",
    "Kwale",
    "Kilifi",
    "Tana River",
    "Lamu",
    "Taita Taveta",
    "Garissa",
    "Wajir",
    "Mandera",
    "Marsabit",
    "Isiolo",
    "Meru",
    "Tharaka Nithi",
    "Embu",
    "Kitui",
    "Machakos",
    "Makueni",
    "Nyandarua",
    "Nyeri",
    "Kirinyaga",
    "Murang'a",
    "Kiambu",
    "Turkana",
    "West Pokot",
    "Samburu",
    "Trans Nzoia",
    "Uasin Gishu",
    "Elgeyo Marakwet",
    "Nandi",
    "Baringo",
    "Laikipia",
    "Nakuru",
    "Narok",
    "Kajiado",
    "Kericho",
    "Bomet",
    "Kakamega",
    "Vihiga",
    "Bungoma",
    "Busia",
    "Siaya",
    "Kisumu",
    "Homa Bay",
    "Migori",
    "Kisii",
    "Nyamira",
    "Nairobi",
)


def normalize_county_name(value):
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    for suffix in ("county", "city"):
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    return normalized


OFFICIAL_COUNTY_NUMBERS = {
    normalize_county_name(name): f"{number:03d}"
    for number, name in enumerate(COUNTIES_IN_OFFICIAL_ORDER, start=1)
}


def official_county_number(name):
    """Return 001–047 for a recognised Kenyan county; otherwise None."""
    return OFFICIAL_COUNTY_NUMBERS.get(normalize_county_name(name))
