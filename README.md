# Student Progress Tracker

## Overview

This Student Progress Tracker is a dashboard for visualising student performance. It provides insights into student's mastery over time for both teachers (Teacher View) and students (Student View).

## Portals

| | URL |
|---|---|
| Teacher Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_teacher_portal/> |
| Student Portal | <https://stellar-edu.shinyapps.io/stellar_education_-_student_portal/> |
| Documentation site | <https://mailysg8.github.io/ai-student-progress-tracker/> |

## Where to find what

| If you want to … | Go to … |
|---|---|
| Read the full project documentation | <https://mailysg8.github.io/ai-student-progress-tracker/> (sources in [`docs/`](docs/)) |
| Browse the experiment notebooks (BKT comparison, KC aggregation, edge cases) | [`notebooks/`](notebooks/) — see [`notebooks/README.md`](notebooks/README.md) for a one-line description of each |
| Look at the dashboard source code | [`app.py`](app.py) (Teacher Portal), [`student_app.py`](student_app.py) (Student Portal), and the helpers in [`src/`](src/) |
| See the data pipeline | [`src/pipeline/`](src/pipeline/) and the `make all` target in [`Makefile`](Makefile) |
| Deploy or maintain the live dashboards | [`DEPLOYMENT.md`](DEPLOYMENT.md) |
| Read the proposal report | [`proposal_report/`](proposal_report/) |

## Instructions

You can run this app locally following the instructions below.

A video with a full run-through of the instructions can be found here : [Instruction Video](img/full_instructions.mp4)

### Repository Setup

To set up the repo and environment, follow the video or the instructions below :
<video src="img/repo_setup.mp4" controls width="100%"></video>
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

<video src="img/data_setup.mp4" controls width="100%"></video>

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

<video src="img/run_app.mp4" controls width="100%"></video>

1. Run the app in reload mode: 
    - Teacher View : 
    ```bash
    shiny run --reload app.py
    ```
    - Student View :
    ```bash
    shiny run --reload student_app.py
    ```


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
> - Files to test it can be found in [`data/csv`](https://github.com/mailysg8/ai-student-progress-tracker/blob/main/data/csv)

<video src="img/data_input.mp4" controls width="100%"></video>

Once data is uploaded, it replaces the current version of `final_student_kc_data.csv` that is used by both dashboards. 

To get the data back to its original state, run the following command in the terminal from the project root:

```bash
make all
```



### Student View

![](img/student-view.gif)
