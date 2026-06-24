# Student Progress Tracker

## Overview

This Student Progress Tracker is a dashboard for visualising student performance. It provides insights into student's mastery over time for both teachers (Teacher View) and students (Student View).

## Instructions

You can run this app locally following the instructions below.

A video with a full run-through of the instructions can be found here : [Instruction Video](img/full_instructions.mp4)

### Repository Setup

To set up the repo and environment, follow the video or the instructions below :
<video src="https://github.com/user-attachments/assets/624da2ab-fb2d-4205-a572-637d860fa2c9" controls width="100%"></video>



1. Clone this repository:

    ```bash
    git clone https://github.com/mailysg8/ai-student-progress-tracker.git
    ```

2. Navigate to the project directory locally:

    ```bash
    cd ai-student-progress-tracker
    ```

3. Install the required dependencies:

    ```bash
    conda env create -f environment.yml
    conda activate stellar-proj
    ```

> **Note on `pybkt` installation.** Because installing `pybkt` directly from PyPI causes issues on macOS, the repository bundles a custom wheel built for **macOS ARM** at `wheels/pybkt-1.4.1-cp311-cp311-macosx_11_0_arm64.whl`. The `environment.yml` installs this local wheel by default.
>
> **If you are not on macOS ARM** (e.g. Linux, Windows, or Intel Mac), open `environment.yml`, find the pip section, and replace:
>
> ```
>     - ./wheels/pybkt-1.4.1-cp311-cp311-macosx_11_0_arm64.whl
> ```
>
> with:
>
> ```
>     - pyBKT==1.4.1
> ```
>
> Then re-run `conda env create -f environment.yml` to install `pyBKT 1.4.1` directly from PyPI.

### Initial Data Setup

For the initial data setup, the following data files are required :

- Student Observations : File containing student attempts on questions as rows 
- Class Plan : File containing classes as rows
- MKC Weights : File containing rank and weight for each MKC
- KC_Map : File containing the mapping from KC to MKC as rows

They should be placed in the `data/raw` folder.

To create the dataframe, follow the video or instructions below :

<video src="https://github.com/user-attachments/assets/d889721b-536d-4b67-8799-0776f4e4b45d" controls width="100%"></video>


1. Create a `.env` file in the project root (an example of what needs to be included can be found in the [`.env.example`](https://github.com/mailysg8/ai-student-progress-tracker/blob/main/.env.example) file)
    - Run the following command in the terminal to copy the `.env.example` file :

    ```bash
    cp .env.example .env
    ```
    

3. Run the following commands in the terminal (make sure you are in the project root) to create the data frame needed for the dashboard :

    ```bash
    make all
    ```
There should now be a file called `final_student_kc_data.csv` in `data/processed` folder.

### Running the App

To run the app locally, follow the video or the instructions below : 

<video src="https://github.com/user-attachments/assets/6faeaebd-3b24-45c8-a822-2ad3b58546d2" controls width="100%"></video>

1. Run the app in reload mode: 
    - Teacher View : 
    ```bash
    shiny run --reload app.py
    ```
    - Student View :
    ```bash
    shiny run --reload student_app.py
    ```


### Regenerating the Report

## Proposal Report
The proposal report is written in [Quarto](https://quarto.org) at [`proposal_report/reports/proposal_report.qmd`](proposal_report/reports/proposal_report.qmd) and produces both a PDF and an HTML version. Quarto is already included in `environment.yml`, so no extra setup is required beyond completing the steps above.

To regenerate the report after editing `proposal_report.qmd`, run from the project root:

```bash
make clean-proposal
make all
make proposal-report
```

This will refresh both `proposal_report.pdf` and `proposal_report.html` in the same folder.

## Final Report
The final report is written in [Quarto](https://quarto.org) at [`proposal_report/final_proposal_report/final_report.qmd`](proposal_report/final_proposal_report/final_report.qmd) and produces both a PDF and an HTML version. Quarto is already included in `environment.yml`, so no extra setup is required beyond completing the steps above.

To regenerate the report after editing `final_report.qmd`, run from the project root:

```bash
make clean-final
make all
make final-report
```

This will refresh both `final_report.pdf` and `final_report.html` in the same folder.


## Demo

The dashboard looks as follows :

### Teacher View

![](img/teacher-view.gif)

More information about the elements found in each the Class Overview Page can be found [here](https://github.com/mailysg8/ai-student-progress-tracker/issues/44).

#### Data Input 

This page allows users to upload data to update the Teacher View.

> **Notes** : 
> - This only works when running the app locally (not on the hosted version of the app).
> - Only csv files can be uploaded. 
> - Sample files are available in [`data/csv`](https://github.com/mailysg8/ai-student-progress-tracker/blob/main/data/csv).

<video src="https://github.com/user-attachments/assets/d916282b-5581-48ad-90bf-a76dc0bf0f0a" controls width="100%"></video>

Once data is uploaded, it replaces the current version of `final_student_kc_data.csv` that is used by both dashboards. 

To get the data back to its original state, run the following command in the terminal from the project root:

```bash
make all
```



### Student View

![](img/student-view.gif)