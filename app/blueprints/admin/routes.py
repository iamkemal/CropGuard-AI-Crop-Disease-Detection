import re
import sqlite3
from math import isfinite
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from app.blueprints.admin import admin_bp
from app.blueprints.auth.routes import roles_required
from app.database import get_db


SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,79}\Z")
RULE_CODE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_]{1,79}\Z")
LOGO_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\.svg\Z")


def _text(field: str, label: str, maximum: int, required: bool = True) -> str:
    value = request.form.get(field, "").strip()
    if required and not value:
        raise ValueError(f"{label} is required.")
    if len(value) > maximum:
        raise ValueError(f"{label} must be no more than {maximum} characters.")
    return value


def _slug(field: str = "slug") -> str:
    value = _text(field, "Slug", 80)
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(
            "Slug must use lowercase letters, numbers, underscores, or hyphens."
        )
    return value


def _integer(field: str, label: str, minimum: int, maximum: int) -> int:
    value = request.form.get(field, "").strip()
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a whole number.") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return number


def _score() -> float:
    value = request.form.get("minimum_score", "").strip()
    try:
        score = float(value)
    except ValueError as error:
        raise ValueError("Minimum score must be a number from 0 to 1.") from error
    if not isfinite(score) or not 0 <= score <= 1:
        raise ValueError("Minimum score must be a number from 0 to 1.")
    return score


def _form_ids(field: str) -> list[int]:
    try:
        values = [int(value) for value in request.form.getlist(field)]
    except ValueError as error:
        raise ValueError("Selections must contain valid record identifiers.") from error
    if len(values) != len(set(values)):
        raise ValueError("Duplicate selections are not allowed.")
    return values


def _validate_symptom_ids(connection, crop_id: int, symptom_ids: list[int]) -> None:
    if not symptom_ids:
        return
    placeholders = ",".join("?" for _ in symptom_ids)
    rows = connection.execute(
        f"""
        SELECT id
        FROM symptoms
        WHERE crop_id = ? AND id IN ({placeholders})
        """,
        (crop_id, *symptom_ids),
    ).fetchall()
    if {int(row["id"]) for row in rows} != set(symptom_ids):
        raise ValueError("Choose only symptoms belonging to the selected crop.")


def _crop_options():
    return get_db().execute(
        "SELECT id, slug, name FROM crops ORDER BY name COLLATE NOCASE"
    ).fetchall()


@admin_bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    connection = get_db()
    counts = {
        "users": connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'farmer'"
        ).fetchone()[0],
        "diseases": connection.execute(
            "SELECT COUNT(*) FROM diseases WHERE is_active = 1"
        ).fetchone()[0],
        "diagnoses": connection.execute(
            "SELECT COUNT(*) FROM diagnoses"
        ).fetchone()[0],
        "rules": connection.execute(
            "SELECT COUNT(*) FROM rules WHERE is_active = 1"
        ).fetchone()[0],
    }
    return render_template("admin/dashboard.html", counts=counts)


@admin_bp.route("/users", methods=["GET"])
@roles_required("admin")
def users():
    records = get_db().execute(
        """
        SELECT id, username, email, is_active, created_at
        FROM users
        WHERE role = 'farmer'
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return render_template("admin/users.html", users=records)


@admin_bp.post("/users/<int:user_id>/toggle")
@roles_required("admin")
def toggle_user(user_id: int):
    connection = get_db()
    user = connection.execute(
        "SELECT role, is_active FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if user is None or user["role"] != "farmer":
        abort(404)
    connection.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (0 if user["is_active"] else 1, user_id),
    )
    connection.commit()
    flash("Farmer account status updated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/delete")
@roles_required("admin")
def delete_user(user_id: int):
    connection = get_db()
    user = connection.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if user is None or user["role"] != "farmer":
        abort(404)
    connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    flash(
        "Farmer account deleted. Its diagnosis history remains and is anonymized.",
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/crops", methods=["GET", "POST"])
@roles_required("admin")
def crops():
    connection = get_db()
    if request.method == "POST":
        try:
            slug = _slug()
            name = _text("name", "Crop name", 80)
            description = _text("description", "Description", 1000)
            logo_filename = _text("logo_filename", "Logo filename", 84)
            _validate_logo(logo_filename)
            is_active = int(request.form.get("is_active", "1") == "1")
            connection.execute(
                """
                INSERT INTO crops (slug, name, description, logo_filename, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (slug, name, description, logo_filename, is_active),
            )
            connection.commit()
        except ValueError as error:
            connection.rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.crops"))
        except sqlite3.IntegrityError:
            connection.rollback()
            flash("A crop with that slug already exists.", "danger")
            return redirect(url_for("admin.crops"))
        flash("Crop created.", "success")
        return redirect(url_for("admin.crops"))

    records = connection.execute(
        "SELECT * FROM crops ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return render_template("admin/crops.html", crops=records)


def _validate_logo(filename: str) -> None:
    if not LOGO_PATTERN.fullmatch(filename) or Path(filename).name != filename:
        raise ValueError("Choose a valid SVG logo filename.")
    logo_path = Path(current_app.static_folder) / "images" / "logos" / filename
    if not logo_path.is_file():
        raise ValueError("The selected logo does not exist in the crop logo folder.")


@admin_bp.route("/crops/<int:crop_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_crop(crop_id: int):
    connection = get_db()
    crop = connection.execute(
        "SELECT * FROM crops WHERE id = ?",
        (crop_id,),
    ).fetchone()
    if crop is None:
        abort(404)
    if request.method == "POST":
        try:
            slug = _slug()
            name = _text("name", "Crop name", 80)
            description = _text("description", "Description", 1000)
            logo_filename = _text("logo_filename", "Logo filename", 84)
            _validate_logo(logo_filename)
            is_active = int(request.form.get("is_active", "1") == "1")
            connection.execute(
                """
                UPDATE crops
                SET slug = ?, name = ?, description = ?, logo_filename = ?,
                    is_active = ?
                WHERE id = ?
                """,
                (slug, name, description, logo_filename, is_active, crop_id),
            )
            connection.commit()
        except ValueError as error:
            connection.rollback()
            flash(str(error), "danger")
            return render_template("admin/crop_form.html", crop=crop), 400
        except sqlite3.IntegrityError:
            connection.rollback()
            flash("A crop with that slug already exists.", "danger")
            return render_template("admin/crop_form.html", crop=crop), 400
        flash("Crop updated.", "success")
        return redirect(url_for("admin.crops"))
    return render_template("admin/crop_form.html", crop=crop)


@admin_bp.post("/crops/<int:crop_id>/delete")
@roles_required("admin")
def delete_crop(crop_id: int):
    connection = get_db()
    try:
        cursor = connection.execute("DELETE FROM crops WHERE id = ?", (crop_id,))
        if cursor.rowcount == 0:
            abort(404)
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        flash(
            "This crop is used by diseases or diagnosis history. Deactivate it instead.",
            "danger",
        )
        return redirect(url_for("admin.crops"))
    flash("Crop deleted.", "success")
    return redirect(url_for("admin.crops"))


@admin_bp.get("/diseases")
@roles_required("admin")
def diseases():
    records = get_db().execute(
        """
        SELECT d.id, d.slug, d.name, d.scientific_name, d.is_active,
               c.name AS crop_name
        FROM diseases AS d
        JOIN crops AS c ON c.id = d.crop_id
        ORDER BY c.name COLLATE NOCASE, d.name COLLATE NOCASE
        """
    ).fetchall()
    return render_template("admin/diseases.html", diseases=records)


def _disease_form_data(disease=None):
    crop_id = int(disease["crop_id"]) if disease is not None else None
    symptoms_by_crop = {}
    for crop in _crop_options():
        symptoms_by_crop[crop["id"]] = get_db().execute(
            """
            SELECT id, slug, label, description
            FROM symptoms
            WHERE crop_id = ? AND is_active = 1
            ORDER BY label COLLATE NOCASE
            """,
            (crop["id"],),
        ).fetchall()
    selected_ids = set()
    key_ids = set()
    if disease is not None:
        links = get_db().execute(
            """
            SELECT symptom_id, is_key
            FROM disease_symptoms
            WHERE disease_id = ?
            """,
            (disease["id"],),
        ).fetchall()
        selected_ids = {row["symptom_id"] for row in links}
        key_ids = {row["symptom_id"] for row in links if row["is_key"]}
    return {
        "disease": disease,
        "crops": _crop_options(),
        "symptoms_by_crop": symptoms_by_crop,
        "selected_ids": selected_ids,
        "key_ids": key_ids,
        "selected_crop_id": crop_id,
    }


def _store_disease(disease_id: int | None = None) -> None:
    connection = get_db()
    crop_id = _integer("crop_id", "Crop", 1, 2_147_483_647)
    crop = connection.execute(
        "SELECT id FROM crops WHERE id = ? AND is_active = 1",
        (crop_id,),
    ).fetchone()
    if crop is None:
        raise ValueError("Choose an active crop.")
    slug = _slug()
    name = _text("name", "Disease name", 120)
    scientific_name = _text("scientific_name", "Scientific name", 160, False)
    description = _text("description", "Description", 3000)
    cause = _text("cause", "Cause", 2000)
    is_active = int(request.form.get("is_active", "1") == "1")
    symptom_ids = _form_ids("symptom_ids")
    key_ids = _form_ids("key_symptom_ids")
    if not set(key_ids).issubset(symptom_ids):
        raise ValueError("Key symptoms must also be selected as disease symptoms.")
    _validate_symptom_ids(connection, crop_id, symptom_ids)

    if disease_id is None:
        cursor = connection.execute(
            """
            INSERT INTO diseases
                (crop_id, slug, name, scientific_name, description, cause, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                crop_id,
                slug,
                name,
                scientific_name or None,
                description,
                cause,
                is_active,
            ),
        )
        disease_id = int(cursor.lastrowid)
    else:
        existing_disease = connection.execute(
            "SELECT crop_id FROM diseases WHERE id = ?",
            (disease_id,),
        ).fetchone()
        if existing_disease is None:
            raise ValueError("The selected disease no longer exists.")
        if int(existing_disease["crop_id"]) != crop_id:
            linked_rules = connection.execute(
                "SELECT COUNT(*) FROM rules WHERE disease_id = ?",
                (disease_id,),
            ).fetchone()[0]
            diagnosis_history = connection.execute(
                "SELECT COUNT(*) FROM diagnosis_candidates WHERE disease_id = ?",
                (disease_id,),
            ).fetchone()[0]
            if linked_rules or diagnosis_history:
                raise ValueError(
                    "A disease with rules or diagnosis history cannot be moved "
                    "to another crop. Create a new disease instead."
                )
        connection.execute(
            """
            UPDATE diseases
            SET crop_id = ?, slug = ?, name = ?, scientific_name = ?,
                description = ?, cause = ?, is_active = ?
            WHERE id = ?
            """,
            (
                crop_id,
                slug,
                name,
                scientific_name or None,
                description,
                cause,
                is_active,
                disease_id,
            ),
        )
        connection.execute(
            "DELETE FROM disease_symptoms WHERE disease_id = ?",
            (disease_id,),
        )

    connection.executemany(
        """
        INSERT INTO disease_symptoms (disease_id, symptom_id, is_key)
        VALUES (?, ?, ?)
        """,
        (
            (disease_id, symptom_id, int(symptom_id in key_ids))
            for symptom_id in symptom_ids
        ),
    )
    connection.commit()


@admin_bp.route("/diseases/new", methods=["GET", "POST"])
@roles_required("admin")
def new_disease():
    if request.method == "POST":
        try:
            _store_disease()
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.new_disease"))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A disease with that slug already exists.", "danger")
            return redirect(url_for("admin.new_disease"))
        flash("Disease created.", "success")
        return redirect(url_for("admin.diseases"))
    return render_template("admin/disease_form.html", **_disease_form_data())


@admin_bp.route("/diseases/<int:disease_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_disease(disease_id: int):
    disease = get_db().execute(
        "SELECT * FROM diseases WHERE id = ?",
        (disease_id,),
    ).fetchone()
    if disease is None:
        abort(404)
    if request.method == "POST":
        try:
            _store_disease(disease_id)
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.edit_disease", disease_id=disease_id))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A disease with that slug already exists.", "danger")
            return redirect(url_for("admin.edit_disease", disease_id=disease_id))
        flash("Disease updated.", "success")
        return redirect(url_for("admin.diseases"))
    return render_template(
        "admin/disease_form.html",
        **_disease_form_data(disease),
    )


@admin_bp.post("/diseases/<int:disease_id>/delete")
@roles_required("admin")
def delete_disease(disease_id: int):
    connection = get_db()
    try:
        cursor = connection.execute(
            "DELETE FROM diseases WHERE id = ?",
            (disease_id,),
        )
        if cursor.rowcount == 0:
            abort(404)
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        flash(
            "This disease appears in diagnosis history. Deactivate it to preserve records.",
            "danger",
        )
        return redirect(url_for("admin.diseases"))
    flash("Disease deleted.", "success")
    return redirect(url_for("admin.diseases"))


@admin_bp.get("/symptoms")
@roles_required("admin")
def symptoms():
    records = get_db().execute(
        """
        SELECT s.id, s.slug, s.label, s.is_active, c.name AS crop_name
        FROM symptoms AS s
        JOIN crops AS c ON c.id = s.crop_id
        ORDER BY c.name COLLATE NOCASE, s.label COLLATE NOCASE
        """
    ).fetchall()
    return render_template("admin/symptoms.html", symptoms=records)


def _store_symptom(symptom_id: int | None = None) -> None:
    connection = get_db()
    crop_id = _integer("crop_id", "Crop", 1, 2_147_483_647)
    crop = connection.execute(
        "SELECT id FROM crops WHERE id = ?",
        (crop_id,),
    ).fetchone()
    if crop is None:
        raise ValueError("Choose an existing crop.")
    slug = _slug()
    label = _text("label", "Symptom label", 160)
    description = _text("description", "Description", 1000)
    is_active = int(request.form.get("is_active", "1") == "1")
    if symptom_id is None:
        connection.execute(
            """
            INSERT INTO symptoms (crop_id, slug, label, description, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (crop_id, slug, label, description, is_active),
        )
    else:
        existing_symptom = connection.execute(
            "SELECT crop_id FROM symptoms WHERE id = ?",
            (symptom_id,),
        ).fetchone()
        if existing_symptom is None:
            raise ValueError("The selected symptom no longer exists.")
        if int(existing_symptom["crop_id"]) != crop_id:
            associations = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM disease_symptoms WHERE symptom_id = ?) +
                    (SELECT COUNT(*) FROM rule_conditions WHERE symptom_id = ?) +
                    (SELECT COUNT(*) FROM diagnosis_symptoms WHERE symptom_id = ?)
                """,
                (symptom_id, symptom_id, symptom_id),
            ).fetchone()[0]
            if associations:
                raise ValueError(
                    "A symptom used by diseases, rules, or diagnoses cannot be "
                    "moved to another crop."
                )
        connection.execute(
            """
            UPDATE symptoms
            SET crop_id = ?, slug = ?, label = ?, description = ?, is_active = ?
            WHERE id = ?
            """,
            (crop_id, slug, label, description, is_active, symptom_id),
        )
    connection.commit()


@admin_bp.route("/symptoms/new", methods=["GET", "POST"])
@roles_required("admin")
def new_symptom():
    if request.method == "POST":
        try:
            _store_symptom()
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.new_symptom"))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A symptom with that slug already exists.", "danger")
            return redirect(url_for("admin.new_symptom"))
        flash("Symptom created.", "success")
        return redirect(url_for("admin.symptoms"))
    return render_template(
        "admin/symptom_form.html",
        symptom=None,
        crops=_crop_options(),
    )


@admin_bp.route("/symptoms/<int:symptom_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_symptom(symptom_id: int):
    symptom = get_db().execute(
        "SELECT * FROM symptoms WHERE id = ?",
        (symptom_id,),
    ).fetchone()
    if symptom is None:
        abort(404)
    if request.method == "POST":
        try:
            _store_symptom(symptom_id)
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.edit_symptom", symptom_id=symptom_id))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A symptom with that slug already exists.", "danger")
            return redirect(url_for("admin.edit_symptom", symptom_id=symptom_id))
        flash("Symptom updated.", "success")
        return redirect(url_for("admin.symptoms"))
    return render_template(
        "admin/symptom_form.html",
        symptom=symptom,
        crops=_crop_options(),
    )


@admin_bp.post("/symptoms/<int:symptom_id>/delete")
@roles_required("admin")
def delete_symptom(symptom_id: int):
    connection = get_db()
    try:
        cursor = connection.execute(
            "DELETE FROM symptoms WHERE id = ?",
            (symptom_id,),
        )
        if cursor.rowcount == 0:
            abort(404)
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        flash(
            "This symptom is used by a disease, rule, or diagnosis. Deactivate it instead.",
            "danger",
        )
        return redirect(url_for("admin.symptoms"))
    flash("Symptom deleted.", "success")
    return redirect(url_for("admin.symptoms"))


def _rule_form_data(rule=None):
    rules_data = None
    if rule is not None:
        conditions = get_db().execute(
            """
            SELECT symptom_id, condition_type
            FROM rule_conditions
            WHERE rule_id = ?
            """,
            (rule["id"],),
        ).fetchall()
        rules_data = {
            "required_ids": {
                row["symptom_id"]
                for row in conditions
                if row["condition_type"] == "required"
            },
            "supporting_ids": {
                row["symptom_id"]
                for row in conditions
                if row["condition_type"] == "supporting"
            },
        }
    return {
        "rule": rule,
        "diseases": get_db().execute(
            """
            SELECT d.id, d.name, d.crop_id, c.name AS crop_name
            FROM diseases AS d
            JOIN crops AS c ON c.id = d.crop_id
            ORDER BY c.name COLLATE NOCASE, d.name COLLATE NOCASE
            """
        ).fetchall(),
        "symptoms": get_db().execute(
            """
            SELECT s.id, s.label, s.description, s.crop_id, c.name AS crop_name
            FROM symptoms AS s
            JOIN crops AS c ON c.id = s.crop_id
            WHERE s.is_active = 1 AND c.is_active = 1
            ORDER BY c.name COLLATE NOCASE, s.label COLLATE NOCASE
            """
        ).fetchall(),
        "rule_conditions": rules_data,
    }


def _store_rule(rule_id: int | None = None) -> None:
    connection = get_db()
    disease_id = _integer("disease_id", "Disease", 1, 2_147_483_647)
    disease = connection.execute(
        "SELECT id, crop_id FROM diseases WHERE id = ? AND is_active = 1",
        (disease_id,),
    ).fetchone()
    if disease is None:
        raise ValueError("Choose an active disease.")
    code = _text("code", "Rule code", 80)
    if not RULE_CODE_PATTERN.fullmatch(code):
        raise ValueError("Rule code must use lowercase letters, numbers, or underscores.")
    name = _text("name", "Rule name", 120)
    description = _text("description", "IF-THEN description", 2000)
    minimum_matches = _integer("minimum_matches", "Minimum matches", 1, 100)
    minimum_score = _score()
    priority = _integer("priority", "Priority", 0, 10000)
    required_ids = _form_ids("required_symptoms")
    supporting_ids = _form_ids("supporting_symptoms")
    if not required_ids:
        raise ValueError("Select at least one required symptom.")
    if set(required_ids) & set(supporting_ids):
        raise ValueError("A symptom cannot be both required and supporting.")
    all_symptom_ids = required_ids + supporting_ids
    if minimum_matches < len(required_ids) or minimum_matches > len(all_symptom_ids):
        raise ValueError(
            "Minimum matches must be at least the required condition count "
            "and no greater than the total selected conditions."
        )
    _validate_symptom_ids(connection, int(disease["crop_id"]), all_symptom_ids)
    is_active = int(request.form.get("is_active", "1") == "1")

    if rule_id is None:
        cursor = connection.execute(
            """
            INSERT INTO rules
                (disease_id, code, name, description, minimum_matches,
                 minimum_score, priority, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disease_id,
                code,
                name,
                description,
                minimum_matches,
                minimum_score,
                priority,
                is_active,
            ),
        )
        rule_id = int(cursor.lastrowid)
    else:
        connection.execute(
            """
            UPDATE rules
            SET disease_id = ?, code = ?, name = ?, description = ?,
                minimum_matches = ?, minimum_score = ?, priority = ?, is_active = ?
            WHERE id = ?
            """,
            (
                disease_id,
                code,
                name,
                description,
                minimum_matches,
                minimum_score,
                priority,
                is_active,
                rule_id,
            ),
        )
        connection.execute(
            "DELETE FROM rule_conditions WHERE rule_id = ?",
            (rule_id,),
        )

    connection.executemany(
        """
        INSERT INTO rule_conditions (rule_id, symptom_id, condition_type, weight)
        VALUES (?, ?, ?, 1.0)
        """,
        (
            (rule_id, symptom_id, condition_type)
            for condition_type, symptom_ids in (
                ("required", required_ids),
                ("supporting", supporting_ids),
            )
            for symptom_id in symptom_ids
        ),
    )
    connection.commit()


@admin_bp.get("/rules")
@roles_required("admin")
def rules():
    records = get_db().execute(
        """
        SELECT r.id, r.code, r.name, r.minimum_matches, r.minimum_score,
               r.is_active, d.name AS disease_name, c.name AS crop_name
        FROM rules AS r
        JOIN diseases AS d ON d.id = r.disease_id
        JOIN crops AS c ON c.id = d.crop_id
        ORDER BY c.name COLLATE NOCASE, d.name COLLATE NOCASE, r.priority, r.code
        """
    ).fetchall()
    return render_template("admin/rules.html", rules=records)


@admin_bp.route("/rules/new", methods=["GET", "POST"])
@roles_required("admin")
def new_rule():
    if request.method == "POST":
        try:
            _store_rule()
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.new_rule"))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A rule with that code already exists.", "danger")
            return redirect(url_for("admin.new_rule"))
        flash("IF-THEN rule created.", "success")
        return redirect(url_for("admin.rules"))
    return render_template("admin/rule_form.html", **_rule_form_data())


@admin_bp.route("/rules/<int:rule_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_rule(rule_id: int):
    rule = get_db().execute(
        "SELECT * FROM rules WHERE id = ?",
        (rule_id,),
    ).fetchone()
    if rule is None:
        abort(404)
    if request.method == "POST":
        try:
            _store_rule(rule_id)
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.edit_rule", rule_id=rule_id))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("A rule with that code already exists.", "danger")
            return redirect(url_for("admin.edit_rule", rule_id=rule_id))
        flash("Rule updated.", "success")
        return redirect(url_for("admin.rules"))
    return render_template("admin/rule_form.html", **_rule_form_data(rule))


@admin_bp.post("/rules/<int:rule_id>/delete")
@roles_required("admin")
def delete_rule(rule_id: int):
    connection = get_db()
    rule = connection.execute(
        "SELECT code FROM rules WHERE id = ?",
        (rule_id,),
    ).fetchone()
    if rule is None:
        abort(404)
    historical_uses = connection.execute(
        """
        SELECT COUNT(*)
        FROM diagnosis_candidates
        WHERE instr(',' || matched_rule_codes || ',', ',' || ? || ',') > 0
        """,
        (rule["code"],),
    ).fetchone()[0]
    if historical_uses:
        connection.execute(
            "UPDATE rules SET is_active = 0 WHERE id = ?",
            (rule_id,),
        )
        flash("Rule deactivated to preserve past diagnosis explanations.", "success")
    else:
        connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        flash("Rule deleted.", "success")
    connection.commit()
    return redirect(url_for("admin.rules"))


@admin_bp.get("/treatments")
@roles_required("admin")
def treatments():
    records = get_db().execute(
        """
        SELECT t.id, t.category, t.recommendation, t.sort_order,
               d.name AS disease_name, c.name AS crop_name
        FROM treatments AS t
        JOIN diseases AS d ON d.id = t.disease_id
        JOIN crops AS c ON c.id = d.crop_id
        ORDER BY c.name COLLATE NOCASE, d.name COLLATE NOCASE,
                 t.category, t.sort_order, t.id
        """
    ).fetchall()
    return render_template("admin/treatments.html", treatments=records)


def _store_treatment(treatment_id: int | None = None) -> None:
    connection = get_db()
    disease_id = _integer("disease_id", "Disease", 1, 2_147_483_647)
    disease = connection.execute(
        "SELECT id FROM diseases WHERE id = ?",
        (disease_id,),
    ).fetchone()
    if disease is None:
        raise ValueError("Choose an existing disease.")
    category = request.form.get("category", "").strip()
    if category not in {"treatment", "prevention"}:
        raise ValueError("Choose treatment or prevention.")
    recommendation = _text("recommendation", "Recommendation", 2000)
    sort_order = _integer("sort_order", "Display order", 0, 10000)
    if treatment_id is None:
        connection.execute(
            """
            INSERT INTO treatments (disease_id, category, recommendation, sort_order)
            VALUES (?, ?, ?, ?)
            """,
            (disease_id, category, recommendation, sort_order),
        )
    else:
        connection.execute(
            """
            UPDATE treatments
            SET disease_id = ?, category = ?, recommendation = ?, sort_order = ?
            WHERE id = ?
            """,
            (disease_id, category, recommendation, sort_order, treatment_id),
        )
    connection.commit()


@admin_bp.route("/treatments/new", methods=["GET", "POST"])
@roles_required("admin")
def new_treatment():
    if request.method == "POST":
        try:
            _store_treatment()
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(url_for("admin.new_treatment"))
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("That recommendation already exists for the selected disease.", "danger")
            return redirect(url_for("admin.new_treatment"))
        flash("Recommendation created.", "success")
        return redirect(url_for("admin.treatments"))
    return render_template(
        "admin/treatment_form.html",
        treatment=None,
        diseases=_active_diseases(),
    )


def _active_diseases():
    return get_db().execute(
        """
        SELECT d.id, d.name, c.name AS crop_name
        FROM diseases AS d
        JOIN crops AS c ON c.id = d.crop_id
        ORDER BY c.name COLLATE NOCASE, d.name COLLATE NOCASE
        """
    ).fetchall()


@admin_bp.route("/treatments/<int:treatment_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_treatment(treatment_id: int):
    treatment = get_db().execute(
        "SELECT * FROM treatments WHERE id = ?",
        (treatment_id,),
    ).fetchone()
    if treatment is None:
        abort(404)
    if request.method == "POST":
        try:
            _store_treatment(treatment_id)
        except ValueError as error:
            get_db().rollback()
            flash(str(error), "danger")
            return redirect(
                url_for("admin.edit_treatment", treatment_id=treatment_id)
            )
        except sqlite3.IntegrityError:
            get_db().rollback()
            flash("That recommendation already exists for the selected disease.", "danger")
            return redirect(
                url_for("admin.edit_treatment", treatment_id=treatment_id)
            )
        flash("Recommendation updated.", "success")
        return redirect(url_for("admin.treatments"))
    return render_template(
        "admin/treatment_form.html",
        treatment=treatment,
        diseases=_active_diseases(),
    )


@admin_bp.post("/treatments/<int:treatment_id>/delete")
@roles_required("admin")
def delete_treatment(treatment_id: int):
    connection = get_db()
    cursor = connection.execute(
        "DELETE FROM treatments WHERE id = ?",
        (treatment_id,),
    )
    if cursor.rowcount == 0:
        abort(404)
    connection.commit()
    flash("Recommendation deleted.", "success")
    return redirect(url_for("admin.treatments"))


@admin_bp.get("/diagnoses")
@roles_required("admin")
def diagnoses():
    records = get_db().execute(
        """
        SELECT d.id, d.outcome, d.confidence_level, d.created_at, d.image_path,
               c.name AS crop_name, u.username,
               candidate.name AS disease_name
        FROM diagnoses AS d
        JOIN crops AS c ON c.id = d.crop_id
        LEFT JOIN users AS u ON u.id = d.user_id
        LEFT JOIN diagnosis_candidates AS dc
            ON dc.diagnosis_id = d.id AND dc.rank = 1
        LEFT JOIN diseases AS candidate ON candidate.id = dc.disease_id
        ORDER BY d.created_at DESC, d.id DESC
        LIMIT 200
        """
    ).fetchall()
    return render_template("admin/diagnoses.html", diagnoses=records)


@admin_bp.get("/diagnoses/<int:diagnosis_id>")
@roles_required("admin")
def diagnosis_detail(diagnosis_id: int):
    connection = get_db()
    diagnosis = connection.execute(
        """
        SELECT d.id, d.image_path, d.outcome, d.confidence_level, d.explanation,
               d.created_at, c.name AS crop_name, u.username
        FROM diagnoses AS d
        JOIN crops AS c ON c.id = d.crop_id
        LEFT JOIN users AS u ON u.id = d.user_id
        WHERE d.id = ?
        """,
        (diagnosis_id,),
    ).fetchone()
    if diagnosis is None:
        abort(404)
    selected_symptoms = connection.execute(
        """
        SELECT s.label
        FROM diagnosis_symptoms AS ds
        JOIN symptoms AS s ON s.id = ds.symptom_id
        WHERE ds.diagnosis_id = ?
        ORDER BY s.label COLLATE NOCASE
        """,
        (diagnosis_id,),
    ).fetchall()
    candidates = connection.execute(
        """
        SELECT dc.rank, dc.match_score, dc.confidence_level, dc.explanation,
               d.name, d.slug
        FROM diagnosis_candidates AS dc
        JOIN diseases AS d ON d.id = dc.disease_id
        WHERE dc.diagnosis_id = ?
        ORDER BY dc.rank
        """,
        (diagnosis_id,),
    ).fetchall()
    return render_template(
        "admin/diagnosis_detail.html",
        diagnosis=diagnosis,
        selected_symptoms=selected_symptoms,
        candidates=candidates,
    )


@admin_bp.get("/diagnoses/<int:diagnosis_id>/image")
@roles_required("admin")
def diagnosis_image(diagnosis_id: int):
    diagnosis = get_db().execute(
        "SELECT image_path FROM diagnoses WHERE id = ?",
        (diagnosis_id,),
    ).fetchone()
    if diagnosis is None or not diagnosis["image_path"]:
        abort(404)
    filename = diagnosis["image_path"]
    if Path(filename).name != filename:
        abort(404)
    response = send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        filename,
        conditional=True,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@admin_bp.get("/reports")
@roles_required("admin")
def reports():
    connection = get_db()
    by_crop = connection.execute(
        """
        SELECT c.name, COUNT(d.id) AS diagnosis_count
        FROM crops AS c
        LEFT JOIN diagnoses AS d ON d.crop_id = c.id
        GROUP BY c.id
        ORDER BY c.name COLLATE NOCASE
        """
    ).fetchall()
    by_disease = connection.execute(
        """
        SELECT c.name AS crop_name, d.name AS disease_name,
               COUNT(DISTINCT dc.diagnosis_id) AS diagnosis_count
        FROM diseases AS d
        JOIN crops AS c ON c.id = d.crop_id
        LEFT JOIN diagnosis_candidates AS dc ON dc.disease_id = d.id
        GROUP BY d.id
        ORDER BY diagnosis_count DESC, c.name COLLATE NOCASE,
                 d.name COLLATE NOCASE
        """
    ).fetchall()
    by_outcome = connection.execute(
        """
        SELECT outcome, COUNT(*) AS diagnosis_count
        FROM diagnoses
        GROUP BY outcome
        ORDER BY outcome
        """
    ).fetchall()
    summary = {
        "farmers": connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'farmer'"
        ).fetchone()[0],
        "active_farmers": connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'farmer' AND is_active = 1"
        ).fetchone()[0],
        "diagnoses": connection.execute(
            "SELECT COUNT(*) FROM diagnoses"
        ).fetchone()[0],
        "images": connection.execute(
            "SELECT COUNT(*) FROM diagnoses WHERE image_path IS NOT NULL"
        ).fetchone()[0],
    }
    return render_template(
        "admin/reports.html",
        summary=summary,
        by_crop=by_crop,
        by_disease=by_disease,
        by_outcome=by_outcome,
    )
