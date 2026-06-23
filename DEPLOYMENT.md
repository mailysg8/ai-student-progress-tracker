# Deployment Guide

This document explains how to deploy and maintain the **Stellar Education** dashboards (Student Portal + Teacher Portal) on shinyapps.io.

---

## Live URLs

| App | URL |
|---|---|
| **Student Portal** | https://stellar-edu.shinyapps.io/stellar_education_-_student_portal/ |
| **Teacher Portal** | https://stellar-edu.shinyapps.io/stellar_education_-_teacher_portal/ |

---

## Hosting Account

Both dashboards are hosted on **shinyapps.io** under the account `stellar-edu`.

- Admin dashboard: https://www.shinyapps.io/admin/
- Login credentials: shared separately via secure channel
- Free tier limits: 5 apps · 25 active hours / app / month · sleeps after 15 min idle

---

## App IDs (important for redeploys)

Every redeploy MUST include `--app-id <ID>` to avoid overwriting the wrong app. The `rsconnect-python` cache only tracks one deployment per source directory, so without explicit `--app-id` you can accidentally clobber the other portal.

| App | App ID |
|---|---|
| Student Portal | `17524775` |
| Teacher Portal | `17524786` |

To look up the current app IDs at any time, open the shinyapps.io admin dashboard — the `Id` column.

---

## Local development

### 1. Clone and set up

```bash
git clone https://github.com/mailysg8/ai-student-progress-tracker
cd ai-student-progress-tracker

conda env create -f environment.yml -n stellar-proj
conda activate stellar-proj
pip install rsconnect-python
```

### 2. Get the data files

The data files are NOT in git. Place them in the following locations (received via Slack / shared drive):

- `data/raw/final_data.xlsx`
- `data/raw/mkc_mapping_pack_v1.0..xlsx`
- `data/processed/final_student_kc_data.csv`
- `data/processed/mkc_mapping_pack_v1.0..xlsx`

### 3. Run locally

```bash
# Student portal — http://127.0.0.1:8000
shiny run --reload student_app.py

# Teacher portal — http://127.0.0.1:8001
shiny run --reload app.py --port 8001
```

---

## Connecting to shinyapps.io (one-time setup)

Get a deployment token from the shinyapps.io dashboard:

1. Log in to https://www.shinyapps.io/admin/
2. Click your account name (top right) → **Tokens**
3. Click **+ Add Token**
4. Click the token row's "Show" button → **Copy to clipboard with command**
5. Paste in terminal and run:

```bash
rsconnect add \
  --account stellar-edu \
  --name stellar-edu \
  --token YOUR_TOKEN \
  --secret YOUR_SECRET
```

Confirm with:

```bash
rsconnect list
```

You should see `stellar-edu` listed.

---

## Redeploying the Student Portal

Update `student_app.py`, `src/build_student_summary.py`, `src/training_agenda_utils.py`, etc. as needed, then:

```bash
cd ai-student-progress-tracker

rsconnect deploy shiny . \
  --name stellar-edu \
  --app-id 17524775 \
  --title "Stellar Education - Student Portal" \
  --entrypoint student_app \
  --exclude "notebooks/*" \
  --exclude "proposal_report/*" \
  --exclude "**/__pycache__/*" \
  --exclude "*.pyc" \
  --exclude "data/output/*" \
  --exclude "data/raw/Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx" \
  --exclude "data/raw/mkc_weights_dataset.xlsx" \
  --exclude "data/raw/mkc_data-june01.csv" \
  --exclude "data/processed/best_subset_1_data.csv" \
  --exclude "data/processed/data_with_aggregated_kcs.csv" \
  --exclude "environment.yml" \
  --exclude "class_overview_dash.qmd" \
  --exclude "student_summary_dash.qmd" \
  --exclude "theme.scss" \
  --exclude "app.py"
```

Takes 5–10 minutes. Test the URL after deploy completes.

---

## Redeploying the Teacher Portal

Update `app.py` and the supporting modules in `src/`, then:

```bash
cd ai-student-progress-tracker

rsconnect deploy shiny . \
  --name stellar-edu \
  --app-id 17524786 \
  --title "Stellar Education - Teacher Portal" \
  --entrypoint app \
  --exclude "notebooks/*" \
  --exclude "proposal_report/*" \
  --exclude "**/__pycache__/*" \
  --exclude "*.pyc" \
  --exclude "data/output/*" \
  --exclude "data/raw/Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx" \
  --exclude "data/raw/mkc_weights_dataset.xlsx" \
  --exclude "data/raw/mkc_data-june01.csv" \
  --exclude "data/processed/best_subset_1_data.csv" \
  --exclude "data/processed/data_with_aggregated_kcs.csv" \
  --exclude "environment.yml" \
  --exclude "class_overview_dash.qmd" \
  --exclude "student_summary_dash.qmd" \
  --exclude "theme.scss" \
  --exclude "student_app.py"
```

---

## Common issues

### `Forbidden` error during deploy

Cause: rsconnect cache points to an app the current token does not own (usually from an earlier failed/abandoned deploy).

Fix:

```bash
rm -rf rsconnect-python/
```

…then redeploy WITH `--app-id` so the cache rebuilds correctly.

### Build fails with "Wheel has unexpected file name" for pyBKT

Cause: pyBKT 1.4.2 published a broken wheel on PyPI.

Fix: `requirements.txt` already pins `pyBKT==1.4.1`. Don't change it.

### Student URL shows Teacher content (or vice versa)

Cause: deployed without `--app-id`, so the rsconnect cache fell back to whichever app it last knew about and overwrote it.

Fix:

1. Archive the bad app via the dashboard (Settings → Archive → delete from Archived list).
2. `rm -rf rsconnect-python/`
3. Redeploy WITH `--app-id <correct ID>` (see App IDs table above).

### `ModuleNotFoundError: No module named 'plotly'` (or similar)

Cause: a dependency is in `environment.yml` but missing from `requirements.txt`.

Fix: add to `requirements.txt` and redeploy.

### App is sleeping / slow first load

Cause: free tier sleeps apps after 15 min idle. First wake takes ~10 s.

Fix: ignore for normal use. To eliminate, upgrade to a paid tier on shinyapps.io.

---

## App management on shinyapps.io

| Action | How |
|---|---|
| View logs | Dashboard → app name → **Logs** tab |
| Restart app | Dashboard → app name → **Settings** → **Restart** |
| Archive | Dashboard → app name → **Settings** → **Archive** |
| Delete | First archive, then go to **Archived** view → delete |
| Rotate token | Account → Tokens → revoke old → add new → rerun `rsconnect add` |

---

## File structure reference

```
ai-student-progress-tracker/
├── app.py                          ← Teacher Portal entrypoint
├── student_app.py                  ← Student Portal entrypoint
├── environment.yml                 ← conda env definition
├── requirements.txt                ← pip dependencies for shinyapps.io
├── src/
│   ├── build_student_summary.py    ← Student Summary HTML mockup
│   ├── training_agenda_utils.py    ← BKT + Practice Plan helpers
│   ├── data_pipeline.py            ← Unified data pipeline
│   ├── bkt.py                      ← BKT model
│   └── ...                         ← other helpers
└── data/
    ├── raw/                        ← input data (gitignored)
    └── processed/                  ← unified pipeline output (gitignored)
```

---

## Contacts

- Project team: Siting Wang, Mailys Guedon, Godsgift Eseoghena Braimah, Seungmyun Park (UBC MDS Capstone 2026)
- Repo: https://github.com/mailysg8/ai-student-progress-tracker
