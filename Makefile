.PHONY: all check data clean

all :
	python src/pipeline/check.py
	python src/pipeline/data_pipeline.py

## check: validate required columns in all input DataFrames
check:
	python src/pipeline/check.py

## data: create dashboard ready dataframe
data :
	python src/pipeline/data_pipeline.py

clean :
	rm -f data/processed/final_student_kc_data.csv