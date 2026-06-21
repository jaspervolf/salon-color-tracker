-- One row per client. Personal info + scheduling availability notes.
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    email TEXT,
    phone TEXT,
    birthday TEXT,
    availability_notes TEXT,
    created_date TEXT NOT NULL
);

-- One row per appointment/visit. Shared info for that visit -
-- consultation and the overall visual outcome. Color house/series now
-- lives per-formulation (see formula_mixes) since different mixes in
-- the same visit can come from different lines.
-- A client can have many over time (history), each independently editable.
-- created_date is set once; last_edited_date updates every time it's saved.
CREATE TABLE IF NOT EXISTS formulas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    created_date TEXT NOT NULL,
    last_edited_date TEXT NOT NULL,

    consultation_notes TEXT,   -- starting point + desired end result

    results_notes TEXT,        -- Visual Outcome + any client feedback

    FOREIGN KEY (client_id) REFERENCES clients (id)
);

-- One row per individual formulation mixed within a single appointment.
-- A visit might need more than one (e.g. a root formula + a separate
-- gloss/toner), each with its own classification, developer(s), recipe,
-- and development time. sort_order controls Formulation A/B/C ordering.
CREATE TABLE IF NOT EXISTS formula_mixes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    formula_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,

    is_lightener INTEGER DEFAULT 0,      -- 0/1, all four independently checkable
    is_permanent INTEGER DEFAULT 0,
    is_demi_permanent INTEGER DEFAULT 0,
    is_deposit_only INTEGER DEFAULT 0,

    color_house_series TEXT,             -- e.g. "Wella Koleston"

    dev_5 INTEGER DEFAULT 0,             -- developer volumes, also independently
    dev_10 INTEGER DEFAULT 0,            -- checkable (a mix can combine more
    dev_15 INTEGER DEFAULT 0,            -- than one volume)
    dev_20 INTEGER DEFAULT 0,
    dev_25 INTEGER DEFAULT 0,
    dev_30 INTEGER DEFAULT 0,
    dev_40 INTEGER DEFAULT 0,

    mix_details TEXT,           -- the actual recipe/ratios
    development_time TEXT,

    FOREIGN KEY (formula_id) REFERENCES formulas (id)
);
