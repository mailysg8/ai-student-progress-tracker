# Getting Started

A clean local setup takes about 10 minutes.

## Prerequisites

- **Conda** (Miniconda or Anaconda)
- **Git**

## 1. Clone the repository

```bash
git clone https://github.com/mailysg8/ai-student-progress-tracker.git
cd ai-student-progress-tracker
```

## 2. Create the conda environment

```bash
conda env create -f environment.yml
conda activate stellar-proj
```

The environment name (`stellar-proj`) is set in `environment.yml`. The environment pins `pyBKT==1.4.1` (the 1.4.2 wheel on PyPI is broken) and `scikit-learn<1.7` (newer sklearn is incompatible with pyBKT at import time).

## 3. Add the data files

Place the following files in `data/raw/` (the repository does not include them):

- **Student observations** — student attempts on questions, one row per attempt
- **Class plan** — class sessions, one row per session
- **MKC weights** — rank and weight per modeling KC
- **KC map** — fine-KC to modeling-KC mapping

## 4. Configure the data paths

Create a `.env` file in the project root pointing to the four data files. Use [`.env.example`](https://github.com/mailysg8/ai-student-progress-tracker/blob/main/.env.example) as a template.

## 5. Build the unified dataset

From the project root, run:

```bash
make all
```

This produces `data/processed/final_student_kc_data.csv` — the single unified file the dashboards consume.

## 6. Run the apps locally

### Teacher view

```bash
shiny run --reload app.py
```

Open <http://127.0.0.1:8000>.

### Student view

```bash
shiny run --reload student_app.py
```

Open <http://127.0.0.1:8000> and log in with any student ID (for example, `S019`).

!!! tip "Running both at once"
    Each `shiny run` defaults to port 8000. To run both views simultaneously, start one with `--port 8001` (or any free port).

---

## Project structure

```
ai-student-progress-tracker/
├── app.py                          # Teacher view entry point
├── student_app.py                  # Student view entry point
├── environment.yml                 # Conda environment definition
├── requirements.txt                # pip dependencies (used by shinyapps.io)
├── Makefile                        # Pipeline + app workflows
├── .env.example                    # Template for data path configuration
├── src/
│   ├── build_student_summary.py    # Student Summary HTML view
│   ├── training_agenda_utils.py    # BKT helpers + practice-plan logic
│   ├── data_pipeline.py            # Unified pipeline
│   ├── bkt.py                      # BKT model wrapper
│   └── ...                         # Additional view + chart helpers
├── data/
│   ├── raw/                        # Raw inputs (gitignored)
│   └── processed/                  # Pipeline outputs (gitignored)
└── docs/                           # This documentation site
```

## Troubleshooting

See [Deployment → Common issues](deployment.md#common-issues) for the most frequent install and runtime problems.
