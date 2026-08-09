CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector, used from phase 2 onward

CREATE TABLE IF NOT EXISTS retailers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL
);

-- One row per PDF flyer actually ingested. Lets you trace any price back to
-- the exact file it came from, independent of store_products (which gets
-- overwritten weekly and only ever reflects the latest extraction).
CREATE TABLE IF NOT EXISTS source_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_id UUID NOT NULL REFERENCES retailers(id),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    file_path TEXT NOT NULL,          -- path inside the shared downloads/ volume
    page_count INT,
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (retailer_id, week_end)
);

CREATE TABLE IF NOT EXISTS store_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_id UUID NOT NULL REFERENCES retailers(id),
    store_product_key TEXT NOT NULL,
    product_name_raw TEXT NOT NULL,
    category TEXT NOT NULL,
    product_type TEXT NOT NULL,
    brand TEXT,
    unit_size NUMERIC,                -- e.g. 1000 (ml), 500 (g), 10 (pcs)
    unit_measurement TEXT,            -- 'ml' | 'g' | 'pcs' | 'washes' | ...
    fat_percent NUMERIC,
    organic TEXT,
    image_url TEXT,                   -- latest cropped product image path
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
    unit_size NUMERIC,
    unit_measurement TEXT,
    fat_percent NUMERIC,
    organic TEXT,
    image_url TEXT,
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
    source_document_id UUID REFERENCES source_documents(id),
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    current_price NUMERIC NOT NULL,
    original_price NUMERIC,
    offer_type TEXT NOT NULL,
    discount_percent NUMERIC,
    multibuy_required_qty INT,
    multibuy_free_qty INT,
    base_price NUMERIC,                -- Grundpreis: legally required per-unit price
    base_price_unit TEXT,              -- 'kg' | 'l' | '100g' | 'piece'
    base_price_source TEXT NOT NULL DEFAULT 'computed',  -- 'printed' | 'computed' -- printed always wins when both exist
    cropped_image_path TEXT,           -- this week's exact product crop, for visual debugging of bad extractions
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
CREATE INDEX IF NOT EXISTS idx_canonical_type ON canonical_products (category, product_type, unit_size, unit_measurement, fat_percent);
CREATE INDEX IF NOT EXISTS idx_price_offers_week ON price_offers (store_product_id, week_start DESC);
CREATE INDEX IF NOT EXISTS idx_price_offers_source_doc ON price_offers (source_document_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_retailer_week ON source_documents (retailer_id, week_end DESC);

-- Seed retailers. Interspar is its own retailer_id even though it's
-- operationally related to Spar -- different flyer, different prices,
-- treated identically to every other retailer in the pipeline.
INSERT INTO retailers (name, code) VALUES
    ('Billa', 'billa'), ('Spar', 'spar'), ('Interspar', 'interspar'),
    ('Hofer', 'hofer'), ('Lidl', 'lidl'), ('Penny', 'penny')
ON CONFLICT (code) DO NOTHING;