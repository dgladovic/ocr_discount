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


def clean_price(price_str: str | float | int | None) -> float | None:
    if price_str is None or price_str == "N/A":
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not isinstance(price_str, str) or not price_str.strip():
        return None

    s = price_str.strip()

    # Handle European shorthand like "1.699,-" or "1,-"
    s = re.sub(r"([,.])\s*-$", r"\1 00", s)

    # Extract the numeric section (including digits, dots, commas, spaces)
    match = re.search(r"\d[\d\s.,]*", s)
    if not match:
        return None

    num_str = match.group(0).strip().replace(" ", "")

    # Handle thousands vs decimal separators
    if "." in num_str and "," in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            # e.g., "1.699,00" -> dot is thousands, comma is decimal
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            # e.g., "1,699.00" -> comma is thousands, dot is decimal
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        # e.g., "1,69" or "1699,00"
        num_str = num_str.replace(",", ".")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) > 2:
            # e.g., "1.699.00" -> remove thousands dots, keep last decimal dot
            num_str = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(num_str)
    except ValueError:
        return None


def parse_volume_ml(volume_str: str | float | int | None) -> float | None:
    """'1 l' -> 1000.0, '500 ml' -> 500.0, '0,75 l' -> 750.0"""
    if volume_str is None or volume_str == "N/A":
        return None
    if isinstance(volume_str, (int, float)):
        return float(volume_str)
    s = str(volume_str).lower().replace(",", ".").strip()
    match = re.search(r"([\d.]+)\s*(l|ml|liter)", s)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2)
    return value * 1000 if unit in ("l", "liter") else value


def parse_weight_g(weight_str: str | float | int | None) -> float | None:
    """'500 g' -> 500.0, '1 kg' -> 1000.0"""
    if weight_str is None or weight_str == "N/A":
        return None
    if isinstance(weight_str, (int, float)):
        return float(weight_str)
    s = str(weight_str).lower().replace(",", ".").strip()
    match = re.search(r"([\d.]+)\s*(g|kg|gramm)", s)
    if not match:
        return None
    value, unit = float(match.group(1)), match.group(2)
    return value * 1000 if unit == "kg" else value


def parse_percent(percent_str: str | float | int | None) -> float | None:
    """'3,5%' -> 3.5, '-25%' -> 25.0"""
    if percent_str is None or percent_str == "N/A":
        return None
    if isinstance(percent_str, (int, float)):
        return float(abs(percent_str))
    s = str(percent_str).replace(",", ".").strip()
    match = re.search(r"([\d.]+)", s)
    return float(match.group(1)) if match else None


def parse_int_or_none(qty_str: str | int | float | None) -> int | None:
    if qty_str is None or qty_str == "N/A":
        return None
    if isinstance(qty_str, int):
        return qty_str
    if isinstance(qty_str, float):
        return int(qty_str)
    match = re.search(r"(\d+)", str(qty_str))
    return int(match.group(1)) if match else None


def compute_effective_unit_price(current_price: float | None, volume_ml: float | None, weight_g: float | None) -> float | None:
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
        dt_end = datetime.strptime(end_date_str, "%Y-%m-%d")
        context_year = dt_end.year
        context_month = dt_end.month
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