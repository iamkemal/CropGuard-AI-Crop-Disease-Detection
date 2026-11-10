# CropGuard frontend update

This update applies the approved CropGuard brand to the existing Flask application. It was built against repository commit `ff0304a068c3f90439f00bcafdd15dcdbd1b79d5`, which already contains camera capture.

## What changes

- The visible application name becomes **CropGuard**, with the shield-and-leaf logo, evergreen `#166534`, forest `#0F2F25`, mint `#E8F5EC`, maize gold `#EAB308`, and Open Sans.
- Home, About, registration, login, farmer pages, and administrator pages share the new responsive layout.
- Farmers can select symptoms, review their observations, and optionally **Take picture** or **Choose photo** before submitting. The existing camera implementation is retained.
- History and management tables support search, relevant filters, and pagination. These controls operate on records already authorised and returned by the server; the existing administrator diagnosis list still loads at most its most recent 200 records.
- Administrator create/edit forms open in a side drawer where supported. Normal form pages, server validation, CSRF fields, and role permissions remain in use. Deletion asks for confirmation.
- The farmer overview shows their three most recent assessments, with deterministic ordering and the existing ownership restriction.
- Fonts, Bootstrap 5.3.3, icons, and brand assets are served locally. Their licences are included.

Accounts, database paths, uploads, disease rules, and the repository name are unchanged. No database migration or new Python dependency is needed. Uploaded photos continue to serve as documentation; diagnosis uses the selected symptoms and stored rules.

## Apply the ZIP to your existing repository

1. Stop the running Flask server by pressing **Ctrl+C** in its terminal.
2. In GitHub Desktop, select **CropGuard-AI-Crop-Disease-Detection**. Save any existing local changes, then use **Fetch origin** and **Pull origin** if offered.
3. Choose **Repository > Show in Explorer**. Keep this window open. It should contain `run.py`, `requirements.txt`, and the `app` folder. Your usual location is `C:\Users\HCF\Documents\GitHub\CropGuard-AI-Crop-Disease-Detection`.
4. Right-click **CropGuard-Frontend-Update.zip**, choose **Extract All**, and open the extracted **updated-files** folder.
5. Select everything **inside updated-files** and copy it. Paste into the repository folder opened by **Show in Explorer**. The copied `app` folder must merge with the repository's existing `app` folder; do not put the `updated-files` folder itself inside `app`.
6. Choose **Replace the files in the destination** when Windows asks. This ZIP contains only the files changed or added by this update. Keep the rest of the repository in place.
7. In the repository terminal, start the server using the existing virtual environment and your existing configuration:

```powershell
.\.venv\Scripts\python.exe -m flask --app run run --host 127.0.0.1 --port 5000
```

8. Open **http://127.0.0.1:5000** and press **Ctrl+F5** to refresh cached styles and scripts. Keep the server terminal open while using the application.

## Verify and commit

Check the homepage, log in with an existing account, create a diagnosis, go back and forward between symptoms and review, and try the photo controls. Check history search and filters. With an administrator account, open an edit drawer, save a record, and review reports.

Live camera access needs a browser with camera support, permission, and HTTPS or localhost. A physical camera was not available in the review environment; camera lifecycle behaviour was verified with the existing automated tests. File selection, preview, submission, and the private photo viewer were also exercised in the browser.

In GitHub Desktop, use this summary:

```text
Apply CropGuard branding and responsive frontend
```

Choose **Commit to main**, then **Push origin**. This ZIP itself does not update GitHub or your computer until you copy and commit its files.

## Validation completed

- Python 3.12: **38 tests passed, 22 subtests passed**.
- Existing camera JavaScript suite: **13 tests passed**.
- Pylint: **10.00/10**, exit code 0.
- Flake8 syntax and undefined-name checks: exit code 0.
- Browser review: desktop plus a 390 px mobile viewport, navigation, retained symptom selections, diagnosis submission, file preview/upload, protected photo viewer, record filters and pagination, administrator drawer save, and deletion cancellation.

The browser review used an isolated temporary database and disposable test accounts. No review harness, test database, real accounts, virtual environment, secrets, or uploaded user photos are included in the ZIP.

## Optional local checks

From the repository directory with development dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pylint app tests config.py run.py
.\.venv\Scripts\python.exe -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
node --test tests/test_camera_upload.cjs
```
