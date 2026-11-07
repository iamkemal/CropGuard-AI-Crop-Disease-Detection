"""Initialize the SQLite database and load the initial rule-based knowledge base."""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "instance" / "maize_tomato.sqlite3"


CROPS = (
    (
        "maize",
        "Maize",
        "A cereal crop grown for food, feed, and household income.",
        "maize.svg",
    ),
    (
        "tomato",
        "Tomato",
        "A fruiting vegetable crop grown in home gardens and commercial fields.",
        "tomato.svg",
    ),
)


DISEASES = (
    (
        "northern_leaf_blight",
        "maize",
        "Northern Leaf Blight",
        "Exserohilum turcicum",
        (
            "A fungal leaf disease that can cause long, cigar-shaped lesions and "
            "reduce healthy leaf area."
        ),
        (
            "The fungus Exserohilum turcicum infects maize leaves; infected crop "
            "residue can carry it between seasons."
        ),
    ),
    (
        "gray_leaf_spot",
        "maize",
        "Gray Leaf Spot",
        "Cercospora zeae-maydis",
        (
            "A fungal leaf disease characterized by narrow, rectangular lesions, "
            "often limited by leaf veins."
        ),
        (
            "The fungus Cercospora zeae-maydis survives in infected maize residue"
            " and spreads by wind and splashing water."
        ),
    ),
    (
        "common_rust",
        "maize",
        "Common Rust",
        "Puccinia sorghi",
        "A fungal disease that produces raised rust-colored pustules on maize leaves.",
        (
            "The fungus Puccinia sorghi spreads by airborne spores; humid "
            "conditions can favor disease development."
        ),
    ),
    (
        "maize_streak_virus",
        "maize",
        "Maize Streak Virus",
        "Maize streak virus",
        (
            "A viral disease that commonly produces pale yellow streaks running "
            "along the leaf veins and may stunt plants."
        ),
        (
            "Maize streak virus is transmitted by leafhoppers. Infected plants "
            "and susceptible grass hosts can contribute to spread."
        ),
    ),
    (
        "early_blight",
        "tomato",
        "Early Blight",
        "Alternaria linariae",
        (
            "A fungal disease that often starts on older, lower leaves with dark "
            "spots and concentric rings."
        ),
        (
            "Alternaria fungi survive on crop debris and can spread by wind and "
            "water splash; warm, wet weather favors disease."
        ),
    ),
    (
        "late_blight",
        "tomato",
        "Late Blight",
        "Phytophthora infestans",
        (
            "A rapidly developing disease that can affect tomato leaves, stems, "
            "and fruit, especially during cool, wet weather."
        ),
        (
            "The oomycete Phytophthora infestans spreads through spores carried "
            "by wind, rain, irrigation, or contaminated material."
        ),
    ),
    (
        "bacterial_wilt",
        "tomato",
        "Bacterial Wilt",
        "Ralstonia solanacearum species complex",
        (
            "A soil-associated bacterial disease that can cause sudden wilting "
            "while foliage initially remains green."
        ),
        (
            "Ralstonia bacteria persist in soil and can move in contaminated "
            "water, soil, tools, or infected planting material."
        ),
    ),
    (
        "tomato_yellow_leaf_curl_virus",
        "tomato",
        "Tomato Yellow Leaf Curl Virus",
        "Tomato yellow leaf curl virus",
        (
            "A viral disease that can cause yellowing and curling of young "
            "leaves, stunted growth, and flower drop."
        ),
        (
            "The virus is transmitted by adult whiteflies; infected plants and "
            "susceptible host plants can serve as sources."
        ),
    ),
)


SYMPTOMS = (
    (
        "maize",
        "long_cigar_shaped_lesions",
        "Long, cigar-shaped leaf lesions",
        "Elongated gray-green or tan lesions extending along the maize leaf.",
    ),
    (
        "maize",
        "maize_lower_leaf_lesions",
        "Lesions first appear on lower leaves",
        "The earliest visible leaf damage is concentrated on older, lower leaves.",
    ),
    (
        "maize",
        "rectangular_vein_bounded_lesions",
        "Rectangular lesions bounded by leaf veins",
        "Long, narrow lesions with relatively straight sides that stop at leaf veins.",
    ),
    (
        "maize",
        "gray_tan_leaf_lesions",
        "Gray or tan leaf lesions",
        "Leaf spots or lesions become pale tan or gray as they develop.",
    ),
    (
        "maize",
        "brick_red_leaf_pustules",
        "Raised brick-red leaf pustules",
        "Small powdery red-brown pustules break through the leaf surface.",
    ),
    (
        "maize",
        "yellow_flecks_near_pustules",
        "Yellow flecks near leaf pustules",
        "Small chlorotic flecks appear before or around rust pustules.",
    ),
    (
        "maize",
        "black_aging_pustules",
        "Older pustules turn dark or black",
        "Mature rust pustules darken as the spores age.",
    ),
    (
        "maize",
        "yellow_streaks_along_veins",
        "Pale yellow streaks run along leaf veins",
        "Multiple narrow yellow or whitish streaks extend lengthwise along the leaf.",
    ),
    (
        "maize",
        "maize_stunting",
        "Plants are smaller or stunted",
        "Plants show reduced height or growth compared with nearby healthy plants.",
    ),
    (
        "maize",
        "maize_leaf_curl",
        "Leaves are curled or distorted",
        "New or affected leaves appear rolled, curled, or otherwise distorted.",
    ),
    (
        "tomato",
        "dark_lower_leaf_spots",
        "Dark spots start on lower leaves",
        "Small brown to black spots are first noticeable on older, lower tomato leaves.",
    ),
    (
        "tomato",
        "concentric_rings_in_spots",
        "Spots have concentric rings",
        "Dark leaf spots show visible target-like or concentric rings.",
    ),
    (
        "tomato",
        "yellowing_around_leaf_spots",
        "Leaves yellow around spots",
        "Yellowing develops around leaf lesions or spreads across affected lower leaves.",
    ),
    (
        "tomato",
        "water_soaked_irregular_lesions",
        "Irregular water-soaked leaf lesions",
        "Irregular dark or water-soaked lesions appear on tomato leaves, often on newer growth.",
    ),
    (
        "tomato",
        "white_growth_leaf_underside",
        "White growth appears under leaves",
        "White cottony growth may appear on the underside of leaves in humid conditions.",
    ),
    (
        "tomato",
        "firm_brown_fruit_lesions",
        "Firm brown lesions on fruit",
        "Fruit develops firm, brown or leathery lesions that may enlarge.",
    ),
    (
        "tomato",
        "sudden_tomato_wilting",
        "Plants wilt suddenly",
        "Whole plants wilt rapidly, sometimes during the heat of the day.",
    ),
    (
        "tomato",
        "brown_stem_vascular_tissue",
        "Stem vascular tissue is brown",
        "The inner water-conducting tissue of a cut lower stem appears brown or discolored.",
    ),
    (
        "tomato",
        "wilt_without_yellowing",
        "Wilted leaves initially remain green",
        "Leaves and stems wilt while foliage initially shows little or no yellowing.",
    ),
    (
        "tomato",
        "yellowing_young_tomato_leaves",
        "Young leaves turn yellow",
        "New leaves show yellowing, often between veins or along leaf margins.",
    ),
    (
        "tomato",
        "upward_tomato_leaf_curl",
        "Young leaves curl upward",
        "New leaves curl upward or appear crumpled or distorted.",
    ),
    (
        "tomato",
        "tomato_stunting_bushy_growth",
        "Plants are stunted or bushy",
        "Shortened growth produces a compact or bushy appearance.",
    ),
    (
        "tomato",
        "tomato_flower_drop",
        "Flowers drop before fruit set",
        "Flowers fall before fruit forms, reducing the number of fruits.",
    ),
    (
        "tomato",
        "general_yellowing_older_leaves",
        "Older leaves yellow uniformly",
        (
            "Older leaves show general yellowing without the distinctive signs "
            "listed for a disease rule."
        ),
    ),
)


DISEASE_SYMPTOMS = (
    ("northern_leaf_blight", "long_cigar_shaped_lesions", 1.0, 1),
    ("northern_leaf_blight", "maize_lower_leaf_lesions", 0.5, 0),
    ("northern_leaf_blight", "gray_tan_leaf_lesions", 0.5, 0),
    ("gray_leaf_spot", "rectangular_vein_bounded_lesions", 1.0, 1),
    ("gray_leaf_spot", "gray_tan_leaf_lesions", 0.5, 0),
    ("gray_leaf_spot", "maize_lower_leaf_lesions", 0.5, 0),
    ("common_rust", "brick_red_leaf_pustules", 1.0, 1),
    ("common_rust", "yellow_flecks_near_pustules", 0.5, 0),
    ("common_rust", "black_aging_pustules", 0.5, 0),
    ("maize_streak_virus", "yellow_streaks_along_veins", 1.0, 1),
    ("maize_streak_virus", "maize_stunting", 0.5, 0),
    ("maize_streak_virus", "maize_leaf_curl", 0.5, 0),
    ("early_blight", "concentric_rings_in_spots", 1.0, 1),
    ("early_blight", "dark_lower_leaf_spots", 0.5, 0),
    ("early_blight", "yellowing_around_leaf_spots", 0.5, 0),
    ("late_blight", "water_soaked_irregular_lesions", 1.0, 1),
    ("late_blight", "white_growth_leaf_underside", 0.75, 1),
    ("late_blight", "firm_brown_fruit_lesions", 0.5, 0),
    ("bacterial_wilt", "sudden_tomato_wilting", 1.0, 1),
    ("bacterial_wilt", "brown_stem_vascular_tissue", 0.75, 1),
    ("bacterial_wilt", "wilt_without_yellowing", 0.5, 0),
    (
        "tomato_yellow_leaf_curl_virus",
        "yellowing_young_tomato_leaves",
        1.0,
        1,
    ),
    (
        "tomato_yellow_leaf_curl_virus",
        "upward_tomato_leaf_curl",
        1.0,
        1,
    ),
    (
        "tomato_yellow_leaf_curl_virus",
        "tomato_stunting_bushy_growth",
        0.5,
        0,
    ),
    ("tomato_yellow_leaf_curl_virus", "tomato_flower_drop", 0.5, 0),
)


RULES = (
    (
        "maize_northern_leaf_blight",
        "northern_leaf_blight",
        "Northern leaf blight pattern",
        (
            "IF long cigar-shaped maize lesions are present AND at least one "
            "supporting symptom is selected, THEN consider Northern Leaf Blight."
        ),
        2,
        0.25,
        30,
        (
            ("long_cigar_shaped_lesions", "required", 1.0),
            ("maize_lower_leaf_lesions", "supporting", 0.5),
            ("gray_tan_leaf_lesions", "supporting", 0.5),
        ),
    ),
    (
        "maize_gray_leaf_spot",
        "gray_leaf_spot",
        "Gray leaf spot pattern",
        (
            "IF rectangular lesions bounded by maize leaf veins are present AND "
            "at least one supporting symptom is selected, THEN consider Gray Leaf"
            " Spot."
        ),
        2,
        0.25,
        30,
        (
            ("rectangular_vein_bounded_lesions", "required", 1.0),
            ("gray_tan_leaf_lesions", "supporting", 0.5),
            ("maize_lower_leaf_lesions", "supporting", 0.5),
        ),
    ),
    (
        "maize_common_rust",
        "common_rust",
        "Common rust pattern",
        (
            "IF raised brick-red maize leaf pustules are present AND at least one"
            " supporting symptom is selected, THEN consider Common Rust."
        ),
        2,
        0.25,
        30,
        (
            ("brick_red_leaf_pustules", "required", 1.0),
            ("yellow_flecks_near_pustules", "supporting", 0.5),
            ("black_aging_pustules", "supporting", 0.5),
        ),
    ),
    (
        "maize_streak_virus_pattern",
        "maize_streak_virus",
        "Maize streak pattern",
        (
            "IF pale yellow streaks run along maize leaf veins AND at least one "
            "supporting symptom is selected, THEN consider Maize Streak Virus."
        ),
        2,
        0.25,
        30,
        (
            ("yellow_streaks_along_veins", "required", 1.0),
            ("maize_stunting", "supporting", 0.5),
            ("maize_leaf_curl", "supporting", 0.5),
        ),
    ),
    (
        "tomato_early_blight",
        "early_blight",
        "Early blight pattern",
        (
            "IF tomato leaf spots have concentric rings AND at least one "
            "supporting symptom is selected, THEN consider Early Blight."
        ),
        2,
        0.25,
        30,
        (
            ("concentric_rings_in_spots", "required", 1.0),
            ("dark_lower_leaf_spots", "supporting", 0.5),
            ("yellowing_around_leaf_spots", "supporting", 0.5),
        ),
    ),
    (
        "tomato_late_blight_water_soaked",
        "late_blight",
        "Late blight water-soaked lesion pattern",
        (
            "IF irregular water-soaked lesions are present AND at least one "
            "supporting symptom is selected, THEN consider Late Blight."
        ),
        2,
        0.25,
        30,
        (
            ("water_soaked_irregular_lesions", "required", 1.0),
            ("white_growth_leaf_underside", "supporting", 0.75),
            ("firm_brown_fruit_lesions", "supporting", 0.5),
        ),
    ),
    (
        "tomato_late_blight_white_growth",
        "late_blight",
        "Late blight white growth pattern",
        (
            "IF white cottony growth is visible under tomato leaves AND at least "
            "one supporting symptom is selected, THEN consider Late Blight."
        ),
        2,
        0.25,
        31,
        (
            ("white_growth_leaf_underside", "required", 1.0),
            ("water_soaked_irregular_lesions", "supporting", 0.75),
            ("firm_brown_fruit_lesions", "supporting", 0.5),
        ),
    ),
    (
        "tomato_bacterial_wilt",
        "bacterial_wilt",
        "Bacterial wilt pattern",
        (
            "IF sudden tomato wilting or brown stem vascular tissue is present "
            "AND at least one supporting symptom is selected, THEN consider "
            "Bacterial Wilt."
        ),
        2,
        0.25,
        30,
        (
            ("sudden_tomato_wilting", "required", 1.0),
            ("brown_stem_vascular_tissue", "supporting", 0.75),
            ("wilt_without_yellowing", "supporting", 0.5),
        ),
    ),
    (
        "tomato_yellow_leaf_curl_yellowing",
        "tomato_yellow_leaf_curl_virus",
        "Yellow leaf curl yellowing pattern",
        (
            "IF young tomato leaves turn yellow AND at least one supporting "
            "symptom is selected, THEN consider Tomato Yellow Leaf Curl Virus."
        ),
        2,
        0.25,
        30,
        (
            ("yellowing_young_tomato_leaves", "required", 1.0),
            ("upward_tomato_leaf_curl", "supporting", 1.0),
            ("tomato_stunting_bushy_growth", "supporting", 0.5),
            ("tomato_flower_drop", "supporting", 0.5),
        ),
    ),
    (
        "tomato_yellow_leaf_curl_curling",
        "tomato_yellow_leaf_curl_virus",
        "Yellow leaf curl curling pattern",
        (
            "IF young tomato leaves curl upward AND at least one supporting "
            "symptom is selected, THEN consider Tomato Yellow Leaf Curl Virus."
        ),
        2,
        0.25,
        31,
        (
            ("upward_tomato_leaf_curl", "required", 1.0),
            ("yellowing_young_tomato_leaves", "supporting", 1.0),
            ("tomato_stunting_bushy_growth", "supporting", 0.5),
            ("tomato_flower_drop", "supporting", 0.5),
        ),
    ),
)


TREATMENTS = (
    (
        "northern_leaf_blight",
        "treatment",
        (
            "Remove heavily infected plant material where practical. For "
            "fungicide decisions, consult a local crop adviser and use only "
            "products registered for maize in the area, following the label."
        ),
    ),
    (
        "northern_leaf_blight",
        "prevention",
        (
            "Choose locally suitable resistant or tolerant varieties, rotate away"
            " from maize when practical, and manage infected crop residue."
        ),
    ),
    (
        "gray_leaf_spot",
        "treatment",
        (
            "Scout fields and seek local crop-adviser guidance before using a "
            "fungicide; use only locally registered products and follow their "
            "labels."
        ),
    ),
    (
        "gray_leaf_spot",
        "prevention",
        (
            "Use resistant varieties where available, rotate crops, and reduce "
            "infected maize residue through locally appropriate tillage or "
            "residue management."
        ),
    ),
    (
        "common_rust",
        "treatment",
        (
            "Assess disease severity and crop stage with a local adviser. If "
            "treatment is warranted, use only a locally registered product "
            "according to its label."
        ),
    ),
    (
        "common_rust",
        "prevention",
        (
            "Select resistant or tolerant varieties suited to the area and "
            "monitor crops early for rust pustules."
        ),
    ),
    (
        "maize_streak_virus",
        "treatment",
        (
            "There is no curative treatment for plants already infected by the "
            "virus. Remove severely affected plants when practical and seek local"
            " advice about leafhopper management."
        ),
    ),
    (
        "maize_streak_virus",
        "prevention",
        (
            "Use locally recommended resistant varieties, plant at locally "
            "advised times, remove volunteer maize and grass hosts near fields, "
            "and use only locally approved vector-control measures."
        ),
    ),
    (
        "early_blight",
        "treatment",
        (
            "Remove badly affected leaves when practical and avoid working among "
            "wet plants. If fungicides are considered, consult a local adviser "
            "and follow a locally registered product label."
        ),
    ),
    (
        "early_blight",
        "prevention",
        (
            "Rotate away from tomato for 2–3 years where feasible, remove "
            "infected crop debris and volunteer tomatoes, maintain plant vigor, "
            "and avoid prolonged leaf wetness."
        ),
    ),
    (
        "late_blight",
        "treatment",
        (
            "Act promptly: isolate and safely remove heavily infected plants and "
            "fruit. Contact a local crop adviser; use fungicides only when "
            "locally registered and exactly as labeled."
        ),
    ),
    (
        "late_blight",
        "prevention",
        (
            "Inspect plants frequently, avoid prolonged leaf wetness, improve "
            "airflow, and remove volunteer tomato and potato plants that may "
            "carry the pathogen."
        ),
    ),
    (
        "bacterial_wilt",
        "treatment",
        (
            "There is no reliable curative field treatment once plants are "
            "systemically infected. Remove affected plants and avoid moving "
            "contaminated soil or water to healthy areas."
        ),
    ),
    (
        "bacterial_wilt",
        "prevention",
        (
            "Use clean planting material, clean tools, improve drainage, avoid "
            "contaminated irrigation water, and rotate with locally suitable "
            "non-host crops."
        ),
    ),
    (
        "tomato_yellow_leaf_curl_virus",
        "treatment",
        (
            "There is no curative treatment for infected plants. Remove severely "
            "affected plants where practical and manage whiteflies using locally "
            "approved integrated pest-management guidance."
        ),
    ),
    (
        "tomato_yellow_leaf_curl_virus",
        "prevention",
        (
            "Use resistant varieties where available, inspect transplants before "
            "planting, remove infected volunteer hosts, and monitor whiteflies "
            "using locally recommended methods."
        ),
    ),
)


SOURCES = (
    (
        "corn-foliar-diseases",
        "Foliar diseases of corn",
        "University of Minnesota Extension",
        "https://extension.umn.edu/corn-pest-management/foliar-diseases-corn",
    ),
    (
        "corn-gray-leaf-spot",
        "Gray leaf spot of corn",
        "Crop Protection Network",
        "https://cropprotectionnetwork.org/encyclopedia/gray-leaf-spot-of-corn",
    ),
    (
        "corn-common-rust",
        "Common rust of corn",
        "Crop Protection Network",
        "https://cropprotectionnetwork.org/encyclopedia/common-rust-of-corn",
    ),
    (
        "maize-streak-virus",
        "Maize streak virus datasheet",
        "CABI Compendium",
        "https://www.cabi.org/isc/datasheet/34790",
    ),
    (
        "tomato-early-blight",
        "Early blight of tomato",
        "NC State Extension",
        "https://content.ces.ncsu.edu/early-blight-of-tomato",
    ),
    (
        "tomato-late-blight",
        "Tomato late blight",
        "NC State Extension",
        "https://content.ces.ncsu.edu/tomato-late-blight",
    ),
    (
        "tomato-bacterial-wilt",
        "Bacterial wilt of tomato",
        "UF/IFAS Extension",
        "https://edis.ifas.ufl.edu/publication/PP113",
    ),
    (
        "tomato-yellow-leaf-curl-virus",
        "Tomato yellow leaf curl virus",
        "NC State Extension",
        "https://content.ces.ncsu.edu/tomato-yellow-leaf-curl-virus",
    ),
)


DISEASE_SOURCES = (
    ("northern_leaf_blight", "corn-foliar-diseases"),
    ("gray_leaf_spot", "corn-gray-leaf-spot"),
    ("gray_leaf_spot", "corn-foliar-diseases"),
    ("common_rust", "corn-common-rust"),
    ("common_rust", "corn-foliar-diseases"),
    ("maize_streak_virus", "maize-streak-virus"),
    ("early_blight", "tomato-early-blight"),
    ("late_blight", "tomato-late-blight"),
    ("bacterial_wilt", "tomato-bacterial-wilt"),
    ("tomato_yellow_leaf_curl_virus", "tomato-yellow-leaf-curl-virus"),
)


def _lookup_id(
    connection: sqlite3.Connection,
    table: str,
    value: str,
    key_column: str = "slug",
) -> int:
    row = connection.execute(
        f"SELECT id FROM {table} WHERE {key_column} = ?",
        (value,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Missing seeded {table} record: {value}")
    return int(row["id"])


def _seed_knowledge_base(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO crops (slug, name, description, logo_filename)
        VALUES (?, ?, ?, ?)
        """,
        CROPS,
    )
    crop_ids = {
        row["slug"]: row["id"]
        for row in connection.execute("SELECT id, slug FROM crops")
    }

    connection.executemany(
        """
        INSERT OR IGNORE INTO diseases
            (slug, crop_id, name, scientific_name, description, cause)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                slug,
                crop_ids[crop_slug],
                name,
                scientific_name,
                description,
                cause,
            )
            for (
                slug,
                crop_slug,
                name,
                scientific_name,
                description,
                cause,
            ) in DISEASES
        ),
    )
    disease_ids = {
        row["slug"]: row["id"]
        for row in connection.execute("SELECT id, slug FROM diseases")
    }

    connection.executemany(
        """
        INSERT OR IGNORE INTO symptoms (crop_id, slug, label, description)
        VALUES (?, ?, ?, ?)
        """,
        (
            (crop_ids[crop_slug], slug, label, description)
            for crop_slug, slug, label, description in SYMPTOMS
        ),
    )
    symptom_ids = {
        row["slug"]: row["id"]
        for row in connection.execute("SELECT id, slug FROM symptoms")
    }

    connection.executemany(
        """
        INSERT OR IGNORE INTO disease_symptoms
            (disease_id, symptom_id, weight, is_key)
        VALUES (?, ?, ?, ?)
        """,
        (
            (disease_ids[disease_slug], symptom_ids[symptom_slug], weight, is_key)
            for disease_slug, symptom_slug, weight, is_key in DISEASE_SYMPTOMS
        ),
    )

    for (
        code,
        disease_slug,
        name,
        description,
        minimum_matches,
        minimum_score,
        priority,
        conditions,
    ) in RULES:
        connection.execute(
            """
            INSERT OR IGNORE INTO rules
                (disease_id, code, name, description, minimum_matches,
                 minimum_score, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disease_ids[disease_slug],
                code,
                name,
                description,
                minimum_matches,
                minimum_score,
                priority,
            ),
        )
        rule_id = _lookup_id(connection, "rules", code, "code")
        connection.executemany(
            """
            INSERT OR IGNORE INTO rule_conditions
                (rule_id, symptom_id, condition_type, weight)
            VALUES (?, ?, ?, ?)
            """,
            (
                (rule_id, symptom_ids[symptom_slug], condition_type, weight)
                for symptom_slug, condition_type, weight in conditions
            ),
        )

    connection.executemany(
        """
        INSERT OR IGNORE INTO treatments
            (disease_id, category, recommendation, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        (
            (
                disease_ids[disease_slug],
                category,
                recommendation,
                index,
            )
            for index, (disease_slug, category, recommendation) in enumerate(
                TREATMENTS, start=1
            )
        ),
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO sources (slug, title, organization, url)
        VALUES (?, ?, ?, ?)
        """,
        SOURCES,
    )
    source_ids = {
        row["slug"]: row["id"]
        for row in connection.execute("SELECT id, slug FROM sources")
    }
    connection.executemany(
        """
        INSERT OR IGNORE INTO disease_sources (disease_id, source_id)
        VALUES (?, ?)
        """,
        (
            (disease_ids[disease_slug], source_ids[source_slug])
            for disease_slug, source_slug in DISEASE_SOURCES
        ),
    )


def initialize_database(database_path: Path | str = DEFAULT_DATABASE_PATH) -> None:
    """Create the schema and add the initial records without overwriting user data."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            _seed_knowledge_base(connection)


def main() -> None:
    """Initialize and seed the database selected by the command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create the SQLite database and seed the crop knowledge base."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Database file (default: {DEFAULT_DATABASE_PATH})",
    )
    args = parser.parse_args()
    initialize_database(args.database)
    print(f"Database initialized: {args.database.resolve()}")


if __name__ == "__main__":
    main()
