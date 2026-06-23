# Student Progress Tracker

## Overview

This Student Progress Tracker is a dashboard for visualising student performance. It provides insights into student's mastery over time for both teachers (Teacher View) and students (Student View).

## Users

The primary users for the Teacher View dashboard are teachers who want to monitor their student's performance and make data-driven decisions. The primary users for the Student View dashbaord are teachers who want to visualise their progress and get suggestions on what to work on.


## Demo

The dashboard looks as follows :

### Teacher View

![](img/teacher-view.gif)

More information about the elements found in each the Class Overview Page can be found [here](https://github.com/mailysg8/ai-student-progress-tracker/issues/44).

### Student View

![](img/student-view.gif)


## instructions

You can run this app locally following the instructions below.

### Setting up

To set up the workflow, follow the instructions below :
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

### Initial Data Setup

For the initial data setup, the following data files are required :
    - Student Observations : File containing student attempts on questions as rows 
    - Class Plan : File containing classes as rows
    - MKC Weights : File containing rank and weight for each MKC
    - KC_Map : File containing the mapping from KC to MKC as rows

1. Put the files into the `data/raw` folder

2. Create a `.env` file in the project root (an example of what needs to be included can be found in the [.env.example](https://github.com/mailysg8/ai-student-progress-tracker/blob/2b0a6029b68aa8df714f48a969ed0179c6651c18/.env.example) file)

3. Run the following commands in the terminal (make sure you are in the project root) to create the data frame needed for the dashboard :

    ```bash
    make all
    ```
There should now be a file called `final_student_kc_data.csv` in `data/processed` folder.

### Running the App

1. Run the app in reload mode: 
    - Teacher View : 
    ```bash
    shiny run --reload app.py
    ```
    - Student View :
    ```bash
    shiny run --reload student_app.py
    ```
