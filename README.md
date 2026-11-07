# Maize and Tomato Rule-Based Disease Expert System

A Flask and SQLite web application for farmers in Bosaso, Puntland. Farmers select crop symptoms to receive ranked, explainable disease possibilities and recommendations. Uploaded photos are stored with diagnosis records for documentation only; they are never analyzed by the inference engine.

## Features

- Farmer registration, login, diagnosis history, and crop-specific workflows.
- Separate maize and tomato illustrations and symptom lists.
- A database-backed rule engine using transparent IF-THEN production rules.
- Ranked possible diseases, rule evidence, symptom matches, and cautious outcomes for ambiguous, insufficient, or unmatched evidence.
- Treatment and prevention recommendations with disease descriptions and cited agricultural references.
- Optional image uploads for documentation, with browser preview, format/content validation, a 5 MiB request limit, 20-megapixel image limit, re-encoding, generated filenames, and private owner/admin access.
- Role-protected administrator pages for managing users, crops, diseases, symptoms, rules, and recommendations; reviewing diagnoses and images; and viewing reports.
- SQLite foreign keys, parameterized queries, password hashing, CSRF protection, and secure session-cookie settings.

The match score is a rule-coverage score, not a medical or agricultural probability. Results are suggestions for further inspection, not a guaranteed diagnosis. Local crop conditions and pesticide registrations vary; consult a qualified local agricultural adviser and follow product labels.

## Project structure

```text
.
|-- app/
|   |-- __init__.py                 Flask application factory and CLI commands
|   |-- blueprints/
|   |   |-- admin/                  Administrator routes
|   |   |-- auth/                   Registration, login, roles, and logout
|   |   `-- farmer/                 Crop selection, diagnosis, results, history
|   |-- database/
|   |   |-- __init__.py             Per-request SQLite connection lifecycle
|   |   |-- schema.sql              Tables, constraints, and indexes
|   |   `-- seed.py                 Initial crops, diseases, rules, and references
|   |-- services/
|   |   |-- inference_engine.py     Symptom-only IF-THEN inference
|   |   `-- upload_service.py       Image validation and safe storage
|   |-- static/
|   |   |-- css/                    Responsive application styles
|   |   |-- images/logos/           Separate maize and tomato SVG logos
|   |   `-- js/                     Client-side image preview
|   `-- templates/                  Shared, farmer, authentication, and admin pages
|-- instance/                       Generated SQLite database and private uploads
|-- tests/                          Database, inference, auth, workflow, upload, admin tests
|-- config.py                       Environment-based application configuration
|-- requirements.txt                Python dependencies
|-- run.py                           Flask entry point
`-- README.md                        Setup, operation, and project guide
```

The `instance/` folder is created automatically and is excluded from version control. The default database is `instance/maize_tomato.sqlite3`; uploaded images are stored under `instance/uploads/` and are not served as public static files.

## Requirements

- Windows 10/11 (commands below use PowerShell)
- Python 3.12 (the version used for verification)
- Internet access to install the packages listed in `requirements.txt`

## Setup and run

From the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, either allow local activation scripts for your user according to your organization's policy, or invoke the environment interpreter directly as `.\.venv\Scripts\python.exe`.

Set a secret for the current PowerShell session and initialize the database:

```powershell
$env:SECRET_KEY = (& python -c "import secrets; print(secrets.token_hex(32))")
flask --app run init-db
```

The `$env:SECRET_KEY` assignment lasts only for this terminal session. Start the
server from the same terminal. For a stable key across restarts, configure a
persistent environment variable through your development or hosting environment.

The Flask application factory also initializes the schema and seed records when it starts; `init-db` can be safely run again. Create the first administrator interactively (the password is hidden while entered):

```powershell
flask --app run create-admin
```

Start the local development server:

```powershell
python run.py
```

Open the address printed by Flask (normally `http://127.0.0.1:5000`). Register farmer accounts from the website. Do not expose Flask's development server to the public internet.

### Configuration

| Environment variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session and CSRF signing key | Random per process in development; required in production |
| `APP_ENV` | Set to `production` to require `SECRET_KEY` and enable secure session cookies | `development` |
| `DATABASE_PATH` | SQLite database file path | `instance/maize_tomato.sqlite3` |
| `UPLOAD_FOLDER` | Private uploaded-image directory | `instance/uploads` |

For production, set `APP_ENV=production`, provide a securely generated persistent `SECRET_KEY`, serve through a production WSGI server over HTTPS, and protect/backup the database and upload directory. Secure cookies are enabled when the app is configured for production.

## Rule engine and knowledge base

The initial knowledge base covers Northern Leaf Blight, Gray Leaf Spot, Common Rust, and Maize Streak Virus in maize, and Early Blight, Late Blight, Bacterial Wilt, and Tomato Yellow Leaf Curl Virus in tomato. Database seed records include symptoms, IF-THEN rules, treatments, prevention methods, and disease reference links.

The inference service reads only the selected crop and symptom identifiers. It checks active rules, required and supporting symptom conditions, minimum match counts, and weighted match-score thresholds. The result explains matching rules and symptoms, ranks candidates, and distinguishes a match from insufficient evidence or no match. Photos are not passed to this service and there is no machine-learning or deep-learning image classification.

Administrators can update knowledge through the admin pages. Rules associated with historical diagnoses are deactivated rather than removed so past explanations remain interpretable. Keep diagnosis rules and recommendations reviewed against current local agricultural guidance.

## Tests

Run the complete test suite from the project root:

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary databases and upload folders; they do not overwrite the default application database.

### GitHub Actions and local checks

Both workflows use Python 3.12 on Ubuntu 24.04, install the same development
dependencies, and run on pushes and pull requests to `main`. They can also be
started manually from the Actions tab.

- **Pylint** checks all tracked Python files. Its default 10/10 score threshold
  and nonzero failure status are retained.
- **Python tests** checks syntax and undefined names with Flake8, then runs the
  full test suite with pytest.

Run the checks locally from the project root, using the activated environment:

```powershell
python -m pip install -r requirements-dev.txt
python -m pylint app tests config.py run.py
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

Development tool versions are pinned in `requirements-dev.txt` so local and CI
checks use the same Pylint, pytest, and Flake8 versions. Small, documented Pylint
exceptions are scoped to data-record fields, Flask's settings container,
and unittest-managed temporary-directory contexts.
All other diagnostics remain enabled; neither workflow uses `--exit-zero` or
`continue-on-error`.

## Database overview

The normalized schema includes `users`, `crops`, `diseases`, `symptoms`, `disease_symptoms`, `rules`, `rule_conditions`, `treatments`, `diagnoses`, `diagnosis_symptoms`, and `diagnosis_candidates`. `sources` and `disease_sources` store references for the knowledge base. Foreign keys protect relationships and diagnosis records preserve selected symptoms, results, candidate explanations, and image paths.
