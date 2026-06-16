.PHONY: check data

## check: validate required columns in all input DataFrames
check:
	python src/pipeline/check.py

## data: create dashboard ready dataframe
data :
	python src/data_pipeline.py