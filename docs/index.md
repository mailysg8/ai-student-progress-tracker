# Stellar Education

A skill-level progress tracker for AP Statistics, built for Stellar Education as a UBC MDS Capstone project (2026).

A homework score tells a teacher *how much* a student got right — but not *which* skills are behind. This dashboard converts raw homework responses into mastery probabilities for each student–skill pair using **Bayesian Knowledge Tracing (BKT)**, then renders them through an interactive Shiny dashboard with a teacher view and a student view.

---

## Portals

| View | URL |
|---|---|
| Student Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_student_portal/> |
| Teacher Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_teacher_portal/> |

---

## What's in the product

### Teacher view

- **Class Overview** — class-wide KC status with a Unit Mastery grid, KC Progress tabs (Most Important · Needs Attention · Good Progress), and an Opportunity Heatmap showing how much practice each skill has received.
- **Student Overview** — drill-down on one learner: a status summary, every KC with its mastery probability, and a toggle between absolute and relative (class-quantile) grading.

### Student view

- **Student Summary** — KPI cards bucketing skills by BKT mastery (Mastered ≥ 65 % · Progressing 35–64 % · Needs Practice < 35 %), per-unit distribution plots, and click-through drill-downs to every skill.
- **Your Next Steps** — personalised practice recommendations weighted by skill importance, paired with a prerequisite map of the student's current mastery.

Both views are driven by the same unified data pipeline, with mastery estimates updating as new responses come in.

---

## Why Bayesian Knowledge Tracing?

The goal is forward-looking: guide what data to collect next, not grade a class that has already finished. BKT was chosen for four reasons:

1. **Small cohorts** — four parameters per knowledge component produce meaningful estimates from 25 students across 47 KCs, where deep-learning approaches would overfit.
2. **Sequential data** — every attempt by every student on every skill, in order, is exactly the structure BKT was designed to model.
3. **Updates without retraining** — each new response refines a student's mastery estimate immediately.
4. **Interpretable output** — mastery is a single probability between 0 and 1, readable as *"this student has a 73 % chance of having mastered this skill"*.

See [Methodology](methodology.md) for the full reasoning.

---

## Project at a glance

| | |
|---|---|
| Course | UBC Master of Data Science Capstone, 2026 |
| Partner | Stellar Education |
| Cohort | 25 students · 47 modeling knowledge components · 10 units |
| Term | September 2025 – April 2026 |
| Stack | Python · Shiny for Python · pyBKT · Plotly · Altair |
| Source | <https://github.com/mailysg8/ai-student-progress-tracker> |
