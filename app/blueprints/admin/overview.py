"""Admin user management, diagnosis review, dashboard, and reporting views."""

from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

from app.blueprints.admin.blueprint import admin_bp
from app.blueprints.auth.routes import roles_required
from app.database import get_db
from app.services.diagnosis_service import get_diagnosis_symptoms


@admin_bp.get("/dashboard")
@roles_required("admin")
def dashboard():
    """Display administrator totals for farmers, diseases, diagnoses, and rules."""
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
    """List farmer accounts and their active status."""
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
    """Activate or deactivate an existing farmer account."""
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
    """Delete a farmer account while retaining anonymized diagnosis history."""
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


@admin_bp.get("/diagnoses")
@roles_required("admin")
def diagnoses():
    """List recent diagnoses across farmer accounts for administrator review."""
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
    """Display a diagnosis, its selected symptoms, and its ranked candidates."""
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
    selected_symptoms = get_diagnosis_symptoms(connection, diagnosis_id)
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
    """Serve a diagnosis image privately to an authorized administrator."""
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
    """Summarize diagnoses by crop, disease, and outcome alongside user totals."""
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
