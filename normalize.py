"""
Deterministic post-processing. Never trust the model/scraper to do
arithmetic or unit conversion -- both connectors emit clean strings,
this module turns them into typed, comparable values.
"""
import re
from datetime import datetime

from ingestion.schemas import PRODUCT_TYPE_TO_CATEGORY_PREFIX


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:60]


def clean_price(price_str: str | None) -> float | None:
    if not isinstance(price_str, str) or price_str == "N/A" or not price_str.strip():
        return None
    cleaned = price_str.replace("€", "").replace("$", "").replace("Sfr", "").replace(",", ".").strip()
    match = re.match(r"[\d.]+", cleaned)
    return float(match.group(0)) if match else None


def parse_volume_ml(volume_str: str | None) -> float | None:
    """'1 l' -> 1000.0, '500 ml' -> 500.0, '0,75 l' -> 750.0"""
    if not volume_str or volume_str == "N/A":
        return None
    s = volume_str.lower().replace(",", ".").strip()
    match = re.match(r"([\d.]+)\s*(l|ml|liter)", s)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2)
    return value * 1000 if unit in ("l", "liter") else value


def parse_weight_g(weight_str: str | None) -> float | None:
    """'500 g' -> 500.0, '1 kg' -> 1000.0"""
    if not weight_str or weight_str == "N/A":
        return None
    s = weight_str.lower().replace(",", ".").strip()
    match = re.match(r"([\d.]+)\s*(g|kg|gramm)", s)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2)
    return value * 1000 if unit == "kg" else value


def parse_percent(percent_str: str | None) -> float | None:
    """'3,5%' -> 3.5"""
    if not percent_str or percent_str == "N/A":
        return None
    match = re.match(r"([\d,.]+)", percent_str.replace(",", "."))
    return float(match.group(1)) if match else None


def parse_int_or_none(qty_str: str | None) -> int | None:
    if not qty_str or qty_str == "N/A":
        return None
    match = re.match(r"(\d+)", qty_str)
    return int(match.group(1)) if match else None


def compute_effective_unit_price(current_price, volume_ml, weight_g) -> float | None:
    """Price per liter or per kg -- the real basis for cross-product comparison."""
    if current_price is None:
        return None
    base = volume_ml or weight_g
    if not base:
        return None
    return round(current_price / (base / 1000), 2)


def parse_start_date(date_range_str: str | None, end_date_str: str) -> str:
    """Uses end_date_str ('YYYY-MM-DD') for year context to derive a start date."""
    if not date_range_str or date_range_str == "N/A" or not end_date_str:
        return end_date_str
    try:
        context_year = datetime.strptime(end_date_str, "%Y-%m-%d").year
    except ValueError:
        return end_date_str
    match = re.search(r"^(\d{1,2}\.\d{1,2})[\s.\-]", date_range_str.strip())
    if match:
        day_month = match.group(1)
        try:
            temp = f"{day_month.replace('.', '')}{context_year}"
            return datetime.strptime(temp, "%d%m%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return end_date_str


def validate_product_type_category(product_type: str, category: str) -> bool:
    """Flags Gemini returning a productType/category combination that don't belong together."""
    prefix = product_type.split("_")[0]
    expected_category = PRODUCT_TYPE_TO_CATEGORY_PREFIX.get(prefix)
    return expected_category == category


def normalize_offer(raw_offer: dict) -> dict:
    """
    Takes one raw productOffer dict (as returned by either connector, matching
    PRODUCT_OFFER_SCHEMA) and returns it enriched with typed/normalized fields.
    Does NOT touch retailer/week context -- that's added by the pipeline.
    """
    attrs = raw_offer.get("attributes", {})

    volume_ml = parse_volume_ml(attrs.get("volume"))
    weight_g = parse_weight_g(attrs.get("weight"))
    fat_percent = parse_percent(attrs.get("fatPercent"))
    current_price = clean_price(raw_offer.get("currentPrice"))
    original_price = clean_price(raw_offer.get("originalPrice"))

    category = raw_offer.get("category")
    product_type = raw_offer.get("productType")
    type_category_ok = validate_product_type_category(product_type, category) if product_type and category else False

    return {
        **raw_offer,
        "brand": attrs.get("brand") if attrs.get("brand") != "N/A" else None,
        "volume_ml": volume_ml,
        "weight_g": weight_g,
        "fat_percent": fat_percent,
        "alcohol_percent": parse_percent(attrs.get("alcoholPercent")),
        "count": attrs.get("count") if attrs.get("count") != "N/A" else None,
        "organic": attrs.get("organic", "unknown"),
        "current_price_numeric": current_price,
        "original_price_numeric": original_price,
        "discount_percent_numeric": parse_percent(raw_offer.get("discountPercent")),
        "multibuy_required_qty": parse_int_or_none(raw_offer.get("multibuyRequiredQty")),
        "multibuy_free_qty": parse_int_or_none(raw_offer.get("multibuyFreeQty")),
        "effective_unit_price": compute_effective_unit_price(current_price, volume_ml, weight_g),
        "attributes_incomplete": _has_missing_expected_attrs(product_type, attrs),
        "type_category_mismatch": not type_category_ok,
        "store_product_key": slugify(f"{raw_offer.get('productName', '')}|{raw_offer.get('packageSize', '')}"),
    }


def _has_missing_expected_attrs(product_type: str | None, attrs: dict) -> bool:
    """Cheap sanity check: dairy_milk with no fat% and no volume is suspicious."""
    if not product_type:
        return True
    if product_type.startswith("dairy") and attrs.get("fatPercent") == "N/A" and attrs.get("volume") == "N/A":
        return True
    if product_type in ("dairy_milk", "dairy_plant_milk") and attrs.get("volume") == "N/A":
        return True
    return False