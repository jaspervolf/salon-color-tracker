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

-- One row per color formula entry. A client can have many over time (history),
-- each independently editable. created_date is set once; last_edited_date
-- updates every time it's saved.
CREATE TABLE IF NOT EXISTS formulas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    created_date TEXT NOT NULL,
    last_edited_date TEXT NOT NULL,

    consultation_notes TEXT,   -- starting point + desired end result

    brand TEXT,
    line TEXT,

    is_lightener INTEGER DEFAULT 0,      -- 0/1, all four independently checkable
    is_permanent INTEGER DEFAULT 0,
    is_demi_permanent INTEGER DEFAULT 0,
    is_deposit_only INTEGER DEFAULT 0,

    formula_details TEXT,
    developer TEXT,
    processing_time TEXT,
    results_notes TEXT,        -- outcome + any client feedback

    FOREIGN KEY (client_id) REFERENCES clients (id)
);
