# Deployment

The two portals are hosted on **shinyapps.io** under the `stellar-edu` account.

| App | URL | App ID |
|---|---|---|
| Student Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_student_portal/> | `17524775` |
| Teacher Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_teacher_portal/> | `17524786` |

!!! warning "Use `--app-id` for every redeploy"
    The `rsconnect-python` cache only tracks one deployment per source directory. Deploying without `--app-id` will silently overwrite the other portal.

---

## One-time setup

### Get a deployment token

1. Log in at <https://www.shinyapps.io/admin/>
2. Account → Tokens → **+ Add Token**
3. Click **Show** on the token row → **Copy to clipboard with command**
4. Paste in your terminal:

```bash
rsconnect add \
  --account stellar-edu \
  --name stellar-edu \
  --token YOUR_TOKEN \
  --secret YOUR_SECRET
```

5. Verify:

```bash
rsconnect list
```

---

## Redeploying

### Student Portal

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

### Teacher Portal

Same command, but with the teacher app ID and entrypoint:

```bash
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

A redeploy takes 5–10 minutes.

---

## Common issues

### `Forbidden` error during deploy

The rsconnect cache is pointing to an app the current token doesn't own.

```bash
rm -rf rsconnect-python/
```

Then redeploy with `--app-id`.

### Build fails with "Wheel has unexpected file name" for pyBKT

`pyBKT==1.4.2` ships a broken wheel on PyPI. `requirements.txt` pins `pyBKT==1.4.1` to avoid it. Do not relax the pin.

### App crashes at startup with `AttributeError: 'list' object has no attribute 'dtype'`

`scikit-learn>=1.7` is incompatible with `pyBKT==1.4.1` at import time. `requirements.txt` pins `scikit-learn>=1.6.1,<1.7`. Do not relax that constraint until pyBKT supports newer sklearn.

### `Error while loading Python API: No module named 'dotenv'`

`src/data_processing.py` imports `python-dotenv`. Make sure it's listed in **both** `requirements.txt` and the `pip:` section of `environment.yml`.

### Student URL shows Teacher content (or vice versa)

The previous deploy ran without `--app-id` and the cache mapped to the wrong app. Archive the bad app in the admin panel, clear `rsconnect-python/`, and redeploy with the correct `--app-id`.

### Free-tier sleep / slow first load

The free tier sleeps apps after 15 minutes of inactivity. The first request after sleep takes ~10 seconds to wake. Upgrade to a paid tier on shinyapps.io to keep apps always-on.

---

## App management on shinyapps.io

| Action | How |
|---|---|
| View logs | Dashboard → app name → **Logs** tab |
| Restart app | Dashboard → app name → **Settings** → **Restart** |
| Archive | Dashboard → app name → **Settings** → **Archive** |
| Delete | Archive first, then **Archived** view → Delete |
| Rotate token | Account → Tokens → Revoke → **+ Add Token** → rerun `rsconnect add` |
