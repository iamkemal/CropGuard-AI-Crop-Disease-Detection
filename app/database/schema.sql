PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'farmer' CHECK (role IN ('farmer', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    logo_filename TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diseases (
    id INTEGER PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE RESTRICT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    scientific_name TEXT,
    description TEXT NOT NULL,
    cause TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS symptoms (
    id INTEGER PRIMARY KEY,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE RESTRICT,
    slug TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS disease_symptoms (
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    symptom_id INTEGER NOT NULL REFERENCES symptoms(id) ON DELETE RESTRICT,
    weight REAL NOT NULL DEFAULT 1.0 CHECK (weight > 0),
    is_key INTEGER NOT NULL DEFAULT 0 CHECK (is_key IN (0, 1)),
    PRIMARY KEY (disease_id, symptom_id)
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    minimum_matches INTEGER NOT NULL DEFAULT 2 CHECK (minimum_matches > 0),
    minimum_score REAL NOT NULL DEFAULT 0.25 CHECK (minimum_score BETWEEN 0 AND 1),
    priority INTEGER NOT NULL DEFAULT 100,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS rule_conditions (
    id INTEGER PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    symptom_id INTEGER NOT NULL REFERENCES symptoms(id) ON DELETE RESTRICT,
    condition_type TEXT NOT NULL CHECK (condition_type IN ('required', 'supporting')),
    weight REAL NOT NULL DEFAULT 1.0 CHECK (weight > 0),
    UNIQUE (rule_id, symptom_id)
);

CREATE TABLE IF NOT EXISTS treatments (
    id INTEGER PRIMARY KEY,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('treatment', 'prevention')),
    recommendation TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (disease_id, category, recommendation)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS disease_sources (
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    PRIMARY KEY (disease_id, source_id)
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    crop_id INTEGER NOT NULL REFERENCES crops(id) ON DELETE RESTRICT,
    image_path TEXT,
    outcome TEXT NOT NULL CHECK (
        outcome IN ('matched', 'no_match', 'insufficient_evidence')
    ),
    confidence_level TEXT NOT NULL CHECK (
        confidence_level IN ('none', 'low', 'moderate', 'high')
    ),
    explanation TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnosis_symptoms (
    diagnosis_id INTEGER NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
    symptom_id INTEGER NOT NULL REFERENCES symptoms(id) ON DELETE RESTRICT,
    PRIMARY KEY (diagnosis_id, symptom_id)
);

CREATE TABLE IF NOT EXISTS diagnosis_candidates (
    diagnosis_id INTEGER NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE RESTRICT,
    rank INTEGER NOT NULL CHECK (rank > 0),
    match_score REAL NOT NULL CHECK (match_score BETWEEN 0 AND 1),
    confidence_level TEXT NOT NULL CHECK (
        confidence_level IN ('low', 'moderate', 'high')
    ),
    matched_rule_codes TEXT NOT NULL,
    explanation TEXT NOT NULL,
    PRIMARY KEY (diagnosis_id, disease_id),
    UNIQUE (diagnosis_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_diseases_crop_id ON diseases(crop_id);
CREATE INDEX IF NOT EXISTS idx_symptoms_crop_id ON symptoms(crop_id);
CREATE INDEX IF NOT EXISTS idx_rules_disease_id ON rules(disease_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_user_created
    ON diagnoses(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_diagnoses_crop_created
    ON diagnoses(crop_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_diagnosis_candidates_rank
    ON diagnosis_candidates(diagnosis_id, rank);
