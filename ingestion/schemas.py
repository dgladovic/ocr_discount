"""
Shared taxonomy and schema definitions used by BOTH ingestion connectors
(Gemini PDF extractor and the web-scraping connectors), so every raw offer
that lands in extracted_json/ has the exact same shape regardless of source.
"""

# --- CATEGORY TAXONOMY (top level) ---
PREDETERMINED_CATEGORIES = [
    "Fresh Produce (Obst & Gemüse)",
    "Meat & Poultry (Fleisch & Geflügel)",
    "Fish & Seafood (Fisch)",
    "Dairy & Eggs (Milchprodukte & Eier)",
    "Frozen Foods (Tiefkühl)",
    "Pantry & Baking (Grundnahrungsmittel)",
    "Drinks & Beverages (Getränke)",
    "Snacks & Confectionery (Süßwaren & Snacks)",
    "Household & Cleaning (Haushalt)",
    "Pet Supplies (Tiernahrung)",
    "Health & Beauty (Drogerie)",
    "Bread & Bakery (Brot & Gebäck)",
    "Miscellaneous",
]
NORMALIZED_CATEGORY_ENUM = [c.split(" (")[0].strip() for c in PREDETERMINED_CATEGORIES]

# --- PRODUCT TYPE TAXONOMY (second level, category-prefixed) ---
PRODUCT_TYPE_ENUM = [
    "dairy_milk", "dairy_yogurt", "dairy_cheese", "dairy_butter", "dairy_cream",
    "dairy_eggs", "dairy_quark", "dairy_plant_milk",
    "meat_beef", "meat_pork", "meat_chicken", "meat_turkey", "meat_sausage",
    "meat_minced", "meat_deli",
    "fish_fresh", "fish_frozen", "fish_canned", "fish_smoked", "fish_shellfish",
    "produce_fruit", "produce_vegetable", "produce_herbs", "produce_salad",
    "frozen_vegetable", "frozen_meal", "frozen_icecream", "frozen_pizza", "frozen_fish",
    "pantry_pasta", "pantry_rice", "pantry_flour", "pantry_oil", "pantry_canned",
    "pantry_spice", "pantry_sauce", "pantry_baking",
    "drinks_water", "drinks_soda", "drinks_juice", "drinks_beer", "drinks_wine",
    "drinks_spirits", "drinks_coffee", "drinks_tea",
    "snacks_chocolate", "snacks_chips", "snacks_candy", "snacks_cookies", "snacks_nuts",
    "household_detergent", "household_cleaner", "household_paper", "household_dish",
    "pet_dogfood", "pet_catfood", "pet_treats", "pet_accessories",
    "beauty_skincare", "beauty_haircare", "beauty_oral", "beauty_vitamins", "beauty_cosmetics",
    "bakery_bread", "bakery_rolls", "bakery_pastry", "bakery_cake",
    "misc_other",
]

# Maps each product_type prefix to the category it must belong to.
# Used for validation in normalize.py -- catches Gemini assigning a
# productType that doesn't match the category it also returned.
PRODUCT_TYPE_TO_CATEGORY_PREFIX = {
    "dairy": "Dairy & Eggs",
    "meat": "Meat & Poultry",
    "fish": "Fish & Seafood",
    "produce": "Fresh Produce",
    "frozen": "Frozen Foods",
    "pantry": "Pantry & Baking",
    "drinks": "Drinks & Beverages",
    "snacks": "Snacks & Confectionery",
    "household": "Household & Cleaning",
    "pet": "Pet Supplies",
    "beauty": "Health & Beauty",
    "bakery": "Bread & Bakery",
    "misc": "Miscellaneous",
}

OFFER_TYPE_ENUM = [
    "PERCENT_OFF", "FIXED_PRICE", "MULTI_BUY", "BUNDLE",
    "LOYALTY_CARD", "WEEKLY_SPECIAL", "OTHER",
]

ATTRIBUTES_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "brand": {"type": "STRING", "description": "Brand name as printed, e.g. 'NÖM'. Use 'N/A' if not visible."},
        "unitSize": {"type": "STRING", "description": "The package size exactly as printed, whatever kind of unit it is -- e.g. '1 l', '500 g', '10 Stück', '3 Waschladungen'. This covers weight, volume, and countable items in one field. Use 'N/A' if no size/quantity is shown."},
        "fatPercent": {"type": "STRING", "description": "Fat content as printed, e.g. '3,5%'. 'N/A' if not applicable."},
        "alcoholPercent": {"type": "STRING", "description": "Alcohol content as printed, e.g. '5% vol'. 'N/A' if not applicable."},
        "organic": {"type": "STRING", "enum": ["yes", "no", "unknown"], "description": "Whether labeled organic/Bio."},
    },
    "required": ["brand", "unitSize", "fatPercent", "alcoholPercent", "organic"],
}

PRODUCT_OFFER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "productName": {"type": "STRING", "description": "Item name, cleaned of price/date clutter."},
        "category": {"type": "STRING", "enum": NORMALIZED_CATEGORY_ENUM},
        "productType": {"type": "STRING", "enum": PRODUCT_TYPE_ENUM,
                         "description": "Specific sub-type. Must belong to the same category returned above."},
        "attributes": ATTRIBUTES_SCHEMA,
        "searchTags": {"type": "ARRAY", "items": {"type": "STRING"},
                        "description": "5-10 multilingual keywords for fuzzy search indexing."},
        "currentPrice": {"type": "STRING", "description": "Current promo price with currency, e.g. '5.99€'."},
        "originalPrice": {"type": "STRING", "description": "Price before discount. 'N/A' if not shown."},
        "packageSize": {"type": "STRING", "description": "Human-readable size for display, e.g. '530 g'."},
        "unitPrice": {"type": "STRING", "description": "Price per standard unit as printed, e.g. '11.30/kg'. 'N/A' if absent."},
        "offerType": {"type": "STRING", "enum": OFFER_TYPE_ENUM,
                       "description": "The discount mechanism, not just its size."},
        "discountPercent": {"type": "STRING", "description": "e.g. '25%'. 'N/A' unless offerType is PERCENT_OFF."},
        "multibuyRequiredQty": {"type": "STRING", "description": "For MULTI_BUY, qty to purchase e.g. '2'. 'N/A' otherwise."},
        "multibuyFreeQty": {"type": "STRING", "description": "For MULTI_BUY, qty received free e.g. '1'. 'N/A' otherwise."},
        "discount": {"type": "STRING", "description": "Human-readable summary, e.g. '2+1', '-25%'."},
        "availabilityDateRange": {"type": "STRING", "description": "As shown on the flyer. 'N/A' if absent."},
        "pageNumber": {"type": "INTEGER",
                       "description": "1-based page number within the provided batch of images where this offer is located."},
        "boundingBox": {"type": "ARRAY", "items": {"type": "INTEGER"},
                         "description": "[ymin, xmin, ymax, xmax] bounding box tightly framing the product's image, 0-1000 scale."},
    },
    "required": [
        "productName", "category", "productType", "attributes", "searchTags",
        "currentPrice", "packageSize", "offerType", "discount", "availabilityDateRange",
        "pageNumber", "boundingBox",
    ],
}

CATEGORY_ANNOUNCEMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "announcementType": {"type": "STRING", "description": "e.g. 'Category Discount', 'Coupon Required'."},
        "categoryAffected": {"type": "STRING", "description": "e.g. 'All Beer', 'Frozen Pizzas'."},
        "discountValue": {"type": "STRING", "description": "e.g. '25% off', 'Buy 1 Get 1 Free'."},
        "details": {"type": "STRING", "description": "Conditions/exclusions. 'N/A' if none visible."},
        "availabilityDateRange": {"type": "STRING", "description": "'N/A' if not found."},
    },
    "required": ["categoryAffected", "discountValue", "availabilityDateRange"],
}

FLYER_DATA_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "productOffers": {"type": "ARRAY", "items": PRODUCT_OFFER_SCHEMA},
        "categoryAnnouncements": {"type": "ARRAY", "items": CATEGORY_ANNOUNCEMENT_SCHEMA},
    },
    "required": ["productOffers", "categoryAnnouncements"],
}