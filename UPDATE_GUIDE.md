# Sida repository-ga loogu cusboonaysiiyo ZIP-kan

## 1. Soo qaado isbeddellada GitHub

GitHub Desktop ka dooro **CropGuard-AI-Crop-Disease-Detection**. Riix
**Fetch origin**, kadib **Pull origin** haddii uu soo muuqdo. Tani waxay soo
qaadaysaa workflows-kii aad browser-ka ku beddeshay.

## 2. Ku koobiyee code-ka la saxay

1. ZIP-kan ka dooro **Extract All**.
2. Fur folder-ka gudaha ilaa aad aragto `app`, `tests`, `run.py`, iyo
   `requirements.txt`.
3. GitHub Desktop ka riix **Repository > Show in Explorer**.
4. Waxa ku jira folder-ka ZIP-ka oo dhan ku koobiyee folder-ka repository-ga.
   Ku dar `.github`, `.gitignore`, iyo `requirements-dev.txt`.
5. Haddii isku magac files ahi jiraan, dooro **Replace the files in the destination**.

ZIP-ku wuxuu hayaa source-ka project-ka; `.git`, `.venv`, database-ka iyo
uploads-ka `instance/` kuma jiraan. Ku koobiyee files-ka folder-ka repository-ga
adigoo aan tirtirayn folder-kaas.

## 3. U dir GitHub

1. Ku noqo GitHub Desktop oo eeg **Changes**.
2. **Summary** ku qor: `Fix Python CI and resolve Pylint findings`.
3. Riix **Commit to main**, kadib **Push origin**.
4. GitHub ka fur **Actions** oo eeg run-yada commit-ka cusub:
   **Pylint** iyo **Python tests**.

Run-yadii hore ee casaanka ahaa waa taariikhda commits-kii hore. Natiijada
isbeddelkan ka eeg run-yada cusub ee push-kan ka dhasha.

## Waxa la saxay

- Labada workflow waxay isticmaalaan Python 3.12, Ubuntu 24.04, iyo
  `actions/setup-python@v6`.
- `requirements-dev.txt` wuxuu qeexayaa versions-ka Pylint, pytest, iyo Flake8
  ee loo adeegsaday baaritaanka maxalliga ah.
- Docstrings ayaa lagu daray; imports aan la isticmaalin iyo sadar dheer ayaa la saxay.
- Query-ga calaamadaha diagnosis-ka waxaa isticmaala helper ay wadaagaan
  farmer-ka iyo admin-ku.
- Admin overview iyo reports waxaa loo saaray module u gaar ah; blueprint
  definitions-ka ayaa laga soocay views-ka si looga saaro circular imports.
- Inference explanations iyo image encoding waxaa loo kala saaray functions
  yaryar. Qaab-dhismeedka xogta, qoraalka seed-ka, iyo assertions-kii tests-ka
  waa la ilaaliyey.
- Tests-ku waxay wadaagaan fixture leh database iyo upload directory ku meel gaar ah.

Pylint wuxuu hayaa xadka default-ka ee 10/10. Exceptions kooban oo sharaxan
waxay ku kooban yihiin dataclass records, Flask configuration, iyo temporary
directories uu unittest maamulo. Checks-ka kale iyo failure status-ku way shaqaynayaan.

## Baaritaanka maxalliga ah

Python 3.12 ayaa lagu xaqiijiyey:

- Pylint 4.1.3: **10.00/10**, exit code **0**.
- Pytest 9.2.0: **37 passed, 22 subtests passed**.
- Flake8 7.5.0: syntax iyo undefined-name checks way gudbeen.
- Git diff whitespace checks iyo workflow YAML validation way gudbeen.

Gudaha project-ka, adigoo environment-ka dhaqaajiyey:

```powershell
python -m pip install -r requirements-dev.txt
python -m pylint app tests config.py run.py
python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

GitHub-hosted runs-ku waxay bilaabmayaan marka aad commit-ka cusub push-garayso.
