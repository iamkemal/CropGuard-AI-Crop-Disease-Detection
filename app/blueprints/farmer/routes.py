import sqlite3
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from app.blueprints.auth.routes import roles_required
from app.blueprints.farmer import farmer_bp
from app.database import get_db
from app.services.inference_engine import InferenceResult, infer_disease
from app.services.upload_service import UploadValidationError, save_crop_image


@farmer_bp.get("/dashboard")
@roles_required("farmer")
def dashboard():
    connection = get_db()
    user_id = int(g.user["id"])
    diagnosis_count = connection.execute(
        "SELECT COUNT(*) FROM diagnoses WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    latest_diagnosis = connection.execute(
        """
        SELECT d.id, d.outcome, d.created_at, c.name AS crop_name,
               candidate.name AS disease_name
        FROM diagnoses AS d
        JOIN crops AS c ON c.id = d.crop_id
        LEFT JOIN diagnosis_candidates AS dc
            ON dc.diagnosis_id = d.id AND dc.rank = 1
        LEFT JOIN diseases AS candidate ON candidate.id = dc.disease_id
        WHERE d.user_id = ?
        ORDER BY d.created_at DESC, d.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return render_template(
        "farmer/dashboard.html",
        user=g.user,
        diagnosis_count=diagnosis_count,
        latest_diagnosis=latest_diagnosis,
    )


@farmer_bp.get("/crops")
@roles_required("farmer")
def crops():
    available_crops = get_db().execute(
        """
        SELECT slug, name, description, logo_filename
        FROM crops
        WHERE is_active = 1
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()
    return render_template("farmer/crops.html", crops=available_crops)


@farmer_bp.route("/crops/<crop_slug>", methods=["GET", "POST"])
@roles_required("farmer")
def crop_diagnosis(crop_slug: str):
    connection = get_db()
    crop = connection.execute(
        """
        SELECT id, slug, name, description, logo_filename
        FROM crops
        WHERE slug = ? AND is_active = 1
        """,
        (crop_slug,),
    ).fetchone()
    if crop is None:
        abort(404)

    symptoms = connection.execute(
        """
        SELECT slug, label, description
        FROM symptoms
        WHERE crop_id = ? AND is_active = 1
        ORDER BY label COLLATE NOCASE
        """,
        (crop["id"],),
    ).fetchall()
    selected_symptom_slugs = request.form.getlist("symptoms")
    if request.method == "GET":
        return render_template(
            "farmer/diagnose.html",
            crop=crop,
            symptoms=symptoms,
            selected_symptoms=set(),
        )

    try:
        result = infer_disease(connection, crop_slug, selected_symptom_slugs)
    except ValueError as error:
        flash(str(error), "danger")
        return (
            render_template(
                "farmer/diagnose.html",
                crop=crop,
                symptoms=symptoms,
                selected_symptoms=set(selected_symptom_slugs),
            ),
            400,
        )

    uploaded_file = request.files.get("crop_image")
    image_path = None
    if uploaded_file is not None and uploaded_file.filename:
        try:
            image_path = save_crop_image(
                uploaded_file,
                current_app.config["UPLOAD_FOLDER"],
            )
        except UploadValidationError as error:
            flash(str(error), "danger")
            return (
                render_template(
                    "farmer/diagnose.html",
                    crop=crop,
                    symptoms=symptoms,
                    selected_symptoms=set(selected_symptom_slugs),
                ),
                400,
            )

    diagnosis_id = _save_diagnosis(
        connection,
        result,
        int(g.user["id"]),
        int(crop["id"]),
        image_path,
    )
    return redirect(url_for("farmer.diagnosis_result", diagnosis_id=diagnosis_id))


def _save_diagnosis(
    connection: sqlite3.Connection,
    result: InferenceResult,
    user_id: int,
    crop_id: int,
    image_path: str | None,
) -> int:
    try:
        cursor = connection.execute(
            """
            INSERT INTO diagnoses
                (user_id, crop_id, image_path, outcome, confidence_level, explanation)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                crop_id,
                image_path,
                result.outcome,
                result.confidence_level,
                result.explanation,
            ),
        )
        diagnosis_id = int(cursor.lastrowid)

        for symptom in result.selected_symptoms:
            symptom_row = connection.execute(
                "SELECT id FROM symptoms WHERE slug = ?",
                (symptom.slug,),
            ).fetchone()
            if symptom_row is None:
                raise sqlite3.IntegrityError(
                    f"Selected symptom disappeared during diagnosis: {symptom.slug}"
                )
            connection.execute(
                """
                INSERT INTO diagnosis_symptoms (diagnosis_id, symptom_id)
                VALUES (?, ?)
                """,
                (diagnosis_id, int(symptom_row["id"])),
            )

        for rank, candidate in enumerate(result.candidates, start=1):
            matched_rule_codes = ",".join(
                rule.code for rule in candidate.matched_rules
            )
            matched_labels = ", ".join(
                symptom.label for symptom in candidate.matched_symptoms
            )
            candidate_explanation = (
                f"Matched symptoms: {matched_labels}. "
                f"Weighted rule coverage: {candidate.match_score:.0%}."
            )
            connection.execute(
                """
                INSERT INTO diagnosis_candidates
                    (diagnosis_id, disease_id, rank, match_score,
                     confidence_level, matched_rule_codes, explanation)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diagnosis_id,
                    candidate.disease_id,
                    rank,
                    candidate.match_score,
                    candidate.confidence_level,
                    matched_rule_codes,
                    candidate_explanation,
                ),
            )

        connection.commit()
        return diagnosis_id
    except sqlite3.Error:
        connection.rollback()
        if image_path is not None:
            stored_image = Path(current_app.config["UPLOAD_FOLDER"]) / image_path
            stored_image.unlink(missing_ok=True)
        raise


@farmer_bp.get("/diagnoses/<int:diagnosis_id>")
@roles_required("farmer")
def diagnosis_result(diagnosis_id: int):
    connection = get_db()
    diagnosis = connection.execute(
        """
        SELECT d.id, d.image_path, d.outcome, d.confidence_level,
               d.explanation, d.created_at, c.name AS crop_name
        FROM diagnoses AS d
        JOIN crops AS c ON c.id = d.crop_id
        WHERE d.id = ? AND d.user_id = ?
        """,
        (diagnosis_id, int(g.user["id"])),
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
    candidate_rows = connection.execute(
        """
        SELECT dc.disease_id, dc.rank, dc.match_score, dc.confidence_level,
               dc.matched_rule_codes, dc.explanation, d.slug, d.name,
               d.scientific_name, d.description, d.cause
        FROM diagnosis_candidates AS dc
        JOIN diseases AS d ON d.id = dc.disease_id
        WHERE dc.diagnosis_id = ?
        ORDER BY dc.rank
        """,
        (diagnosis_id,),
    ).fetchall()
    candidates = []
    for row in candidate_rows:
        candidate = dict(row)
        rule_codes = [
            code for code in candidate["matched_rule_codes"].split(",") if code
        ]
        candidate["rules"] = []
        for code in rule_codes:
            rule = connection.execute(
                "SELECT code, name, description FROM rules WHERE code = ?",
                (code,),
            ).fetchone()
            if rule is not None:
                candidate["rules"].append(rule)
        candidate["treatments"] = connection.execute(
            """
            SELECT category, recommendation
            FROM treatments
            WHERE disease_id = ?
            ORDER BY category, sort_order, id
            """,
            (candidate["disease_id"],),
        ).fetchall()
        candidate["sources"] = connection.execute(
            """
            SELECT s.title, s.organization, s.url
            FROM disease_sources AS ds
            JOIN sources AS s ON s.id = ds.source_id
            WHERE ds.disease_id = ?
            ORDER BY s.organization, s.title
            """,
            (candidate["disease_id"],),
        ).fetchall()
        candidates.append(candidate)

    return render_template(
        "farmer/result.html",
        diagnosis=diagnosis,
        selected_symptoms=selected_symptoms,
        candidates=candidates,
    )


@farmer_bp.get("/history")
@roles_required("farmer")
def history():
    diagnoses = get_db().execute(
        """
        SELECT d.id, d.outcome, d.confidence_level, d.created_at, d.image_path,
               c.name AS crop_name, candidate.name AS disease_name
        FROM diagnoses AS d
        JOIN crops AS c ON c.id = d.crop_id
        LEFT JOIN diagnosis_candidates AS dc
            ON dc.diagnosis_id = d.id AND dc.rank = 1
        LEFT JOIN diseases AS candidate ON candidate.id = dc.disease_id
        WHERE d.user_id = ?
        ORDER BY d.created_at DESC, d.id DESC
        """,
        (int(g.user["id"]),),
    ).fetchall()
    return render_template("farmer/history.html", diagnoses=diagnoses)


@farmer_bp.get("/diagnoses/<int:diagnosis_id>/image")
@roles_required("farmer")
def diagnosis_image(diagnosis_id: int):
    diagnosis = get_db().execute(
        """
        SELECT image_path
        FROM diagnoses
        WHERE id = ? AND user_id = ?
        """,
        (diagnosis_id, int(g.user["id"])),
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


@farmer_bp.get("/diseases/<disease_slug>")
@roles_required("farmer")
def disease_detail(disease_slug: str):
    connection = get_db()
    disease = connection.execute(
        """
        SELECT d.id, d.slug, d.name, d.scientific_name, d.description, d.cause,
               c.name AS crop_name
        FROM diseases AS d
        JOIN crops AS c ON c.id = d.crop_id
        WHERE d.slug = ? AND d.is_active = 1
        """,
        (disease_slug,),
    ).fetchone()
    if disease is None:
        abort(404)
    symptoms = connection.execute(
        """
        SELECT s.label, s.description, ds.is_key
        FROM disease_symptoms AS ds
        JOIN symptoms AS s ON s.id = ds.symptom_id
        WHERE ds.disease_id = ? AND s.is_active = 1
        ORDER BY ds.is_key DESC, s.label COLLATE NOCASE
        """,
        (disease["id"],),
    ).fetchall()
    treatments = connection.execute(
        """
        SELECT category, recommendation
        FROM treatments
        WHERE disease_id = ?
        ORDER BY category, sort_order, id
        """,
        (disease["id"],),
    ).fetchall()
    sources = connection.execute(
        """
        SELECT s.title, s.organization, s.url
        FROM disease_sources AS ds
        JOIN sources AS s ON s.id = ds.source_id
        WHERE ds.disease_id = ?
        ORDER BY s.organization, s.title
        """,
        (disease["id"],),
    ).fetchall()
    return render_template(
        "farmer/disease_detail.html",
        disease=disease,
        symptoms=symptoms,
        treatments=treatments,
        sources=sources,
    )


@farmer_bp.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    flash("Images must be no larger than 5 MB.", "danger")
    return render_template("errors/413.html"), 413
