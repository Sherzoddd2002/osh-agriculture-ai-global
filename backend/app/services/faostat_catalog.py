"""FAOSTAT crop-item taxonomy for user-facing catalog and forecast governance.

FAOSTAT QCL contains individual crop items, group aggregates, and some product
forms. Keep every source item in the database; classify it at read time so raw
observations and provenance remain unchanged.
"""
from __future__ import annotations

import re
import unicodedata


CROP = "CROP"
AGGREGATE = "AGGREGATE"
PRODUCT_FORM = "PRODUCT_FORM"

ITEM_TYPE_LABELS = {
    CROP: "Alohida ekin itemi",
    AGGREGATE: "Yig‘ma/agregat ko‘rsatkich",
    PRODUCT_FORM: "Mahsulot shakli",
}

# Explicit FAOSTAT QCL item identifiers. These are source catalog items, not
# observations and are deliberately not deleted from the imported dataset.
AGGREGATE_ITEM_CODES = frozenset({
    "1717",   # Cereals, primary
    "1804",   # Citrus Fruit, Total
    "17530",  # Fibre Crops, Fibre Equivalent
    "1738",   # Fruit Primary
    "1841",   # Oilcrops, Cake Equivalent
    "1732",   # Oilcrops, Oil Equivalent
    "1726",   # Pulses, Total
    "1720",   # Roots and Tubers, Total
    "1723",   # Sugar Crops Primary
    "1729",   # Treenuts, Total
    "1735",   # Vegetables Primary
})
PRODUCT_FORM_ITEM_CODES = frozenset({
    "836",    # Natural rubber in primary forms
})


def _clean_code(value: object) -> str:
    raw = str(value or "").strip().lstrip("'").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    return raw.lstrip("0") or "0"


def _normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def classify_faostat_item(item_code: object, crop_name: object) -> str:
    """Return CROP, AGGREGATE, or PRODUCT_FORM for a FAOSTAT QCL item."""
    code = _clean_code(item_code)
    if code in PRODUCT_FORM_ITEM_CODES:
        return PRODUCT_FORM
    if code in AGGREGATE_ITEM_CODES:
        return AGGREGATE

    name = _normalized_name(crop_name)
    # A conservative fallback for future QCL catalog updates. Explicit product
    # forms above take precedence over words such as "primary".
    if re.search(r"\b(total|equivalent)\b", name):
        return AGGREGATE
    if re.search(r"\bprimary\b", name):
        return AGGREGATE
    return CROP


def item_type_label(item_type: str) -> str:
    return ITEM_TYPE_LABELS.get(item_type, "Noma’lum toifa")
