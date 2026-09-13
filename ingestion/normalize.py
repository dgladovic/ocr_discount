"""
Deterministic post-processing. Never trust the model to do arithmetic or
unit conversion -- the connector emits clean strings, this module turns
them into typed, comparable values.
"""
import re
import unicodedata
from datetime import datetime

from ingestion.schemas import PRODUCT_TYPE_TO_CATEGORY_PREFIX

# Known Austrian flyer filler phrases that describe the offer/display, not
# the product -- Gemini has been observed folding these into productName.
# Maintained list, reviewed periodically against real override corrections
# (see specs/07-name-quality-feedback-loop.md).
_VARIANT_NOISE_PATTERNS = [
    r"\bversch\.?\s*sorten\b", r"\bverschiedene\s*sorten\b", r"\bdiv\.?\s*sorten\b",
    r"\bmehrere\s*sorten\b", r"\bsort\.?\b", r"\bbunt\s*gemischt\b", r"\bbunt\b",
    r"\bim\s*sortiment\b", r"\bnach\s*wahl\b",
]
_VARIANT_NOISE_RE = re.compile("|".join(_VARIANT_NOISE_PATTERNS), re.IGNORECASE)

# Unit synonyms -> normalized unit_measurement value.
_WEIGHT_UNITS = {"g": "g", "gramm": "g", "kg": "g"}       # kg normalizes to g (x1000)
_VOLUME_UNITS = {"ml": "ml", "l": "ml", "liter": "ml"}    # l normalizes to ml (x1000)
_COUNT_UNITS = {
    "stück": "pcs", "stk": "pcs", "pcs": "pcs", "pc": "pcs",
    "waschladungen": "washes", "wl": "washes",
    "blatt": "sheets", "rollen": "rolls", "rolle": "rolls",
}
_BASE_PRICE_UNIT_MAP = {"kg": "kg", "l": "l", "liter": "l", "100g": "100g", "100ml": "100g", "stk": "piece", "stück": "piece"}

# Legal-entity suffixes that sometimes tag along on a brand string and would
# otherwise fork an identical brand into two canonical products.
_BRAND_LEGAL_SUFFIX_RE = re.compile(r"\b(gmbh|ag|kg|e\.?gen\.?|og|co\.?)\b\.?\s*$", re.IGNORECASE)
_TRADEMARK_SYMBOLS_RE = re.compile(r"[®™©]")

# Multipack notation Gemini sometimes transcribes verbatim, e.g. '6x0,5l',
# '4 x 250 ml', '3x400g' -- must be resolved to a total size BEFORE the
# generic single-unit regex below, or '6x0,5l' silently mis-parses as
# (6.0, 'x'), an invalid/garbage unit_measurement.
_MULTIPACK_RE = re.compile(r"(\d+)\s*x\s*(\d+(?:[.,]\d+)?)\s*([a-zäöü]+)", re.IGNORECASE)


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:60]


def strip_variant_noise(name: str) -> str:
    """Removes known filler/variant-disclaimer phrases, collapses extra whitespace."""
    if not name:
        return name
    cleaned = _VARIANT_NOISE_RE.sub("", name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,-")
    return cleaned or name  # never return an empty string


def normalize_brand(brand: str | None) -> str | None:
    """
    Collapses casing/whitespace/symbol variants of the same brand so
    'ACTIV ENERGY' and 'Activ Energy' produce the identical stored string
    and therefore match during canonical resolution, instead of silently
    forking into two canonical products.

    Trade-off: this title-cases everything, including brands that are
    intentionally stylized in caps (e.g. a brand legitimately called
    'NORMA'). That's accepted here because consistent matching matters more
    than preserving stylization -- if a specific canonical product's
    *display* casing needs to look a particular way, fix it via
    product_overrides on that one row; it won't affect matching, since
    matching happens on this normalized value computed at ingestion time,
    not on the overridden display value.
    """
    if not brand or brand == "N/A":
        return None
    text = unicodedata.normalize("NFC", str(brand))
    text = _TRADEMARK_SYMBOLS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _BRAND_LEGAL_SUFFIX_RE.sub("", text).strip(" .,-")
    if not text:
        return None
    return " ".join(word.capitalize() for word in text.split())


def clean_price(price_str: str | float | int | None) -> float | None:
    if price_str is None or price_str == "N/A":
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not isinstance(price_str, str) or not price_str.strip():
        return None

    s = price_str.strip()
    s = re.sub(r"([,.])\s*-$", r"\1 00", s)  # "1,-" -> "1, 00"
    match = re.search(r"\d[\d\s.,]*", s)
    if not match:
        return None
    num_str = match.group(0).strip().replace(" ", "")

    if "." in num_str and "," in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        num_str = num_str.replace(",", ".")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) > 2:
            num_str = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return round(float(num_str), 2)
    except ValueError:
        return None


def _normalize_single_unit(value: float, unit_raw: str) -> tuple[float, str]:
    unit_raw = unit_raw.lower()
    if unit_raw in _WEIGHT_UNITS:
        return (round(value * 1000, 2), "g") if unit_raw == "kg" else (round(value, 2), "g")
    if unit_raw in _VOLUME_UNITS:
        return (round(value * 1000, 2), "ml") if unit_raw in ("l", "liter") else (round(value, 2), "ml")
    if unit_raw in _COUNT_UNITS:
        return round(value, 2), _COUNT_UNITS[unit_raw]
    return round(value, 2), unit_raw  # unrecognized unit kept verbatim rather than dropped


def parse_unit_size(size_str: str | None) -> tuple[float | None, str | None]:
    """
    Parses a transcribed size string into (numeric_value, normalized_unit).
    Handles weight, volume, count-based units, AND multipack notation
    uniformly:
      '1 l' -> (1000.0, 'ml')          '500 g' -> (500.0, 'g')
      '10 Stück' -> (10.0, 'pcs')      '6x0,5l' -> (3000.0, 'ml')  [total, not per-bottle]
      '4 x 250 ml' -> (1000.0, 'ml')   '3 Waschladungen' -> (3.0, 'washes')

    Rounds to 2 decimal places -- avoids two genuinely-identical sizes
    silently failing to match in resolution due to binary float noise
    (e.g. 330.00000000000006 vs 330.0) picked up during repeated parsing.
    """
    if not size_str or size_str == "N/A":
        return None, None
    s = str(size_str).lower().replace(",", ".").strip()

    multipack_match = _MULTIPACK_RE.search(s)
    if multipack_match:
        count = int(multipack_match.group(1))
        try:
            per_item_value = float(multipack_match.group(2))
        except ValueError:
            return None, None
        per_item_value, unit = _normalize_single_unit(per_item_value, multipack_match.group(3))
        if unit in ("g", "ml"):  # total makes sense for weight/volume
            return round(count * per_item_value, 2), unit
        return per_item_value, unit  # counts/washes/etc: multipack notation doesn't apply the same way

    match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zäöü]+)", s)
    if not match:
        return None, None
    try:
        value = float(match.group(1))
    except ValueError:
        return None, None
    return _normalize_single_unit(value, match.group(2))


def parse_base_price(unit_price_str: str | None) -> tuple[float | None, str | None]:
    """'11.30/kg' -> (11.30, 'kg'); '2,49/Stk' -> (2.49, 'piece'); 'N/A' -> (None, None)."""
    if not unit_price_str or unit_price_str == "N/A":
        return None, None
    s = str(unit_price_str).lower().strip()
    if "/" not in s:
        return None, None
    price_part, unit_part = s.split("/", 1)
    price = clean_price(price_part)
    unit_part = re.sub(r"[^a-z0-9]", "", unit_part)
    unit = _BASE_PRICE_UNIT_MAP.get(unit_part)
    return (price, unit) if price is not None and unit else (None, None)


def compute_base_price_fallback(current_price: float | None, unit_size: float | None,
                                 unit_measurement: str | None) -> tuple[float | None, str | None]:
    """
    Fallback when the flyer prints no Grundpreis: derive price per kg/l/piece
    from the current price and package size. Always inferior to a printed
    value -- caller sets base_price_source accordingly.
    """
    if current_price is None or not unit_size or not unit_measurement:
        return None, None
    if unit_measurement == "g":
        return round(current_price / (unit_size / 1000), 2), "kg"
    if unit_measurement == "ml":
        return round(current_price / (unit_size / 1000), 2), "l"
    if unit_measurement == "pcs":
        return round(current_price / unit_size, 2), "piece"
    return None, None  # no sensible base price for e.g. 'washes', 'sheets'


def parse_percent(percent_str: str | float | int | None) -> float | None:
    if percent_str is None or percent_str == "N/A":
        return None
    if isinstance(percent_str, (int, float)):
        return round(float(abs(percent_str)), 2)
    s = str(percent_str).replace(",", ".").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", s)
    if not match:
        return None
    try:
        return round(float(match.group(1)), 2)
    except ValueError:
        return None


def parse_int_or_none(qty_str: str | int | float | None) -> int | None:
    if qty_str is None or qty_str == "N/A":
        return None
    if isinstance(qty_str, int):
        return qty_str
    if isinstance(qty_str, float):
        return int(qty_str)
    match = re.search(r"(\d+)", str(qty_str))
    return int(match.group(1)) if match else None


def parse_start_date(date_range_str: str | None, end_date_str: str) -> str:
    if not date_range_str or date_range_str == "N/A" or not end_date_str:
        return end_date_str
    try:
        dt_end = datetime.strptime(end_date_str, "%Y-%m-%d")
        context_year, context_month = dt_end.year, dt_end.month
    except ValueError:
        return end_date_str
    match = re.search(r"(\d{1,2})\.(\d{1,2})", date_range_str.strip())
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        try:
            start_year = context_year - 1 if month > context_month else context_year
            return datetime(start_year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return end_date_str


def validate_product_type_category(product_type: str, category: str) -> bool:
    prefix = product_type.split("_")[0]
    return PRODUCT_TYPE_TO_CATEGORY_PREFIX.get(prefix) == category


def normalize_offer(raw_offer: dict) -> dict:
    """
    Takes one raw productOffer dict (matching PRODUCT_OFFER_SCHEMA) and
    returns it enriched with typed/normalized fields. Does NOT touch
    retailer/week/source-document context -- that's added by the pipeline.
    """
    attrs = raw_offer.get("attributes", {})

    unit_size, unit_measurement = parse_unit_size(attrs.get("unitSize"))
    fat_percent = parse_percent(attrs.get("fatPercent"))
    current_price = clean_price(raw_offer.get("currentPrice"))
    original_price = clean_price(raw_offer.get("originalPrice"))

    base_price, base_price_unit = parse_base_price(raw_offer.get("unitPrice"))
    base_price_source = "printed"
    if base_price is None:
        base_price, base_price_unit = compute_base_price_fallback(current_price, unit_size, unit_measurement)
        base_price_source = "computed"

    category = raw_offer.get("category")
    product_type = raw_offer.get("productType")
    type_category_ok = validate_product_type_category(product_type, category) if product_type and category else False

    product_name_clean = strip_variant_noise(raw_offer.get("productName", ""))

    return {
        **raw_offer,
        "product_name_clean": product_name_clean,
        "brand": normalize_brand(attrs.get("brand")),
        "unit_size": unit_size,
        "unit_measurement": unit_measurement,
        "fat_percent": fat_percent,
        "alcohol_percent": parse_percent(attrs.get("alcoholPercent")),
        "organic": attrs.get("organic", "unknown"),
        "current_price_numeric": current_price,
        "original_price_numeric": original_price,
        "discount_percent_numeric": parse_percent(raw_offer.get("discountPercent")),
        "multibuy_required_qty": parse_int_or_none(raw_offer.get("multibuyRequiredQty")),
        "multibuy_free_qty": parse_int_or_none(raw_offer.get("multibuyFreeQty")),
        "base_price": base_price,
        "base_price_unit": base_price_unit,
        "base_price_source": base_price_source,
        "attributes_incomplete": _has_missing_expected_attrs(product_type, attrs),
        "type_category_mismatch": not type_category_ok,
        "store_product_key": slugify(f"{product_name_clean}|{raw_offer.get('packageSize', '')}"),
    }


def _has_missing_expected_attrs(product_type: str | None, attrs: dict) -> bool:
    if not product_type:
        return True
    if product_type.startswith("dairy") and attrs.get("fatPercent") == "N/A" and attrs.get("unitSize") == "N/A":
        return True
    if product_type in ("dairy_milk", "dairy_plant_milk") and attrs.get("unitSize") == "N/A":
        return True
    return False