CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector, used from phase 2 onward

CREATE TABLE IF NOT EXISTS retailers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS store_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_id UUID NOT NULL REFERENCES retailers(id),
    store_product_key TEXT NOT NULL,
    product_name_raw TEXT NOT NULL,
    category TEXT NOT NULL,
    product_type TEXT NOT NULL,
    brand TEXT,
    volume_ml NUMERIC,
    weight_g NUMERIC,
    fat_percent NUMERIC,
    organic TEXT,
    image_url TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (retailer_id, store_product_key)
);

CREATE TABLE IF NOT EXISTS canonical_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL,
    category TEXT NOT NULL,
    product_type TEXT NOT NULL,
    brand TEXT,
    volume_ml NUMERIC,
    weight_g NUMERIC,
    fat_percent NUMERIC,
    organic TEXT,
    embedding VECTOR(768),
    is_manually_edited BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS store_product_links (
    store_product_id UUID PRIMARY KEY REFERENCES store_products(id),
    canonical_id UUID NOT NULL REFERENCES canonical_products(id),
    confidence NUMERIC NOT NULL DEFAULT 1.0,
    match_method TEXT NOT NULL DEFAULT 'exact'
);

CREATE TABLE IF NOT EXISTS price_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_product_id UUID NOT NULL REFERENCES store_products(id),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    current_price NUMERIC NOT NULL,
    original_price NUMERIC,
    offer_type TEXT NOT NULL,
    discount_percent NUMERIC,
    multibuy_required_qty INT,
    multibuy_free_qty INT,
    effective_unit_price NUMERIC,
    availability_date_range TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (store_product_id, week_start)
);

CREATE TABLE IF NOT EXISTS category_announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_id UUID NOT NULL REFERENCES retailers(id),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    announcement_type TEXT,
    category_affected TEXT NOT NULL,
    discount_value TEXT NOT NULL,
    details TEXT,
    availability_date_range TEXT
);

CREATE TABLE IF NOT EXISTS product_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id UUID NOT NULL REFERENCES canonical_products(id),
    field_name TEXT NOT NULL,
    override_value TEXT NOT NULL,
    edited_by TEXT NOT NULL,
    edited_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_id, field_name)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    canonical_id UUID REFERENCES canonical_products(id),
    match_mode TEXT NOT NULL DEFAULT 'product',
    group_filter JSONB,
    threshold_price NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_store_products_type ON store_products (category, product_type);
CREATE INDEX IF NOT EXISTS idx_canonical_type ON canonical_products (category, product_type, volume_ml, fat_percent);
CREATE INDEX IF NOT EXISTS idx_price_offers_week ON price_offers (store_product_id, week_start DESC);

-- Seed the five retailers
INSERT INTO retailers (name, code) VALUES
    ('Billa', 'billa'), ('Spar', 'spar'), ('Hofer', 'hofer'),
    ('Lidl', 'lidl'), ('Penny', 'penny'), ('Interspar', 'interspar')
ON CONFLICT (code) DO NOTHING;