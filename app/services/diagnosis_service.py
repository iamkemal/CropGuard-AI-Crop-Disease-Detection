"""Read diagnosis evidence shared by farmer and administrator views."""

import sqlite3


def get_diagnosis_symptoms(
    connection: sqlite3.Connection,
    diagnosis_id: int,
) -> list[sqlite3.Row]:
    """Return the selected symptom labels in display order for one diagnosis."""
    return connection.execute(
        """
        SELECT s.label
        FROM diagnosis_symptoms AS ds
        JOIN symptoms AS s ON s.id = ds.symptom_id
        WHERE ds.diagnosis_id = ?
        ORDER BY s.label COLLATE NOCASE
        """,
        (diagnosis_id,),
    ).fetchall()
