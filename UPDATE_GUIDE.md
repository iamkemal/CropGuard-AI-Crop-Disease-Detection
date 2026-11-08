# How to update the repository using this ZIP

## 1. Pull the latest changes from GitHub

In GitHub Desktop, select **CropGuard-AI-Crop-Disease-Detection**. Click
**Fetch origin**, then **Pull origin** if it appears. This downloads the
workflow changes you made in the browser.

## 2. Copy the corrected code

1. Right-click this ZIP file and select **Extract All**.
2. Open the inner project folder until you see `app`, `tests`, `run.py`, and
   `requirements.txt`.
3. In GitHub Desktop, select **Repository > Show in Explorer**.
4. Copy all the contents of the extracted project folder into the repository
   folder. Include `.github`, `.gitignore`, and `requirements-dev.txt`.
5. If files with the same names already exist, choose
   **Replace the files in the destination**.

The ZIP contains the project's source code. It does not include `.git`,
`.venv`, the database, or the uploads stored in `instance/`. Copy the files
into the existing repository folder without deleting that folder.

## 3. Push the changes to GitHub

1. Return to GitHub Desktop and review **Changes**.
2. In **Summary**, enter: `Fix Python CI and resolve Pylint findings`.
3. Click **Commit to main**, then **Push origin**.
4. On GitHub, open **Actions** and check the runs for the new commit:
   **Pylint** and **Python tests**.

The earlier failed runs remain as part of the history of previous commits.
Check the new runs triggered by this push to see the results of these changes.

## What was fixed

- Both workflows use Python 3.12, Ubuntu 24.04, and
  `actions/setup-python@v6`.
- `requirements-dev.txt` specifies the versions of Pylint, pytest, and Flake8
  used for local verification.
- Docstrings were added, unused imports were removed, and long lines were
  corrected.
- Diagnosis symptom queries use a shared helper for the farmer and admin
  views.
- The admin overview and reports were moved into a separate module. Blueprint
  definitions were separated from views to eliminate circular imports.
- Inference explanations and image encoding were split into smaller
  functions. Data structures, seed text, and test assertions were preserved.
- Tests share fixtures with a temporary database and upload directory.

Pylint retains its default 10/10 score threshold. Limited, documented
exceptions are scoped to dataclass records, Flask configuration, and temporary
directories managed by unittest. All other checks and failure exit statuses
remain enabled.

## Local verification

Verified using Python 3.12:

- Pylint 4.1.3: **10.00/10**, exit code **0**.
- Pytest 9.2.0: **37 passed, 22 subtests passed**.
- Flake8 7.5.0: syntax and undefined-name checks passed.
- Git diff whitespace checks and workflow YAML validation passed.

From the project directory, with the virtual environment activated:

```powershell
python -m pip install -r requirements-dev.txt
python -m pylint app tests config.py run.py
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

GitHub-hosted runs will start after you push the new commit.

