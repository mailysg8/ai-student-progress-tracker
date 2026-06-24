# This Makefile automates the report and pipeline workflows
#
# Usage:
#   make all               - Check the data contains all the necessary columns and create final_student_kc_data.csv 
#	make check             - Check the data contains all the necessary columns
#  	make data              - Create final_student_kc_data.csv 
#   make proposal-report   - Create the proposal report
#   make final-report      - Create the final report
#   make clean-all         - Remove all generated files
#   make clean-final       - Remove all generated files related to final report
#   make clean-proposal    - Remove all generated files related to proposal report

.PHONY: all check data proposal-report final-report clean-all clean-final clean-proposal

all :
	python src/pipeline/check.py
	python src/pipeline/data_pipeline.py

# ===================== CHECK =====================
check:
	python src/pipeline/check.py

# ===================== DATA =====================
data : 
	python src/pipeline/data_pipeline.py

# ===================== PROPOSAL-REPORT =====================
proposal_report/reports/proposal_report.html: proposal_report/reports/proposal_report.qmd \
		proposal_report/figures/kc_coverage.png \
		proposal_report/figures/kc_coverage_comparison.png \
		proposal_report/figures/performance_band.png \
		proposal_report/tables/kc_coverage_comparison_table.csv \
		proposal_report/tables/kc_summary.csv \
		proposal_report/tables/missing_assignment.csv \
		proposal_report/tables/missing_student_assignment.csv \
		proposal_report/tables/perf_summary.csv \
		proposal_report/tables/student_summary.csv
	quarto render proposal_report/reports/proposal_report.qmd --to html

proposal_report/reports/proposal_report.pdf: proposal_report/reports/proposal_report.qmd \
		proposal_report/figures/kc_coverage.png \
		proposal_report/figures/kc_coverage_comparison.png \
		proposal_report/figures/performance_band.png \
		proposal_report/tables/kc_coverage_comparison_table.csv \
		proposal_report/tables/kc_summary.csv \
		proposal_report/tables/missing_assignment.csv \
		proposal_report/tables/missing_student_assignment.csv \
		proposal_report/tables/perf_summary.csv \
		proposal_report/tables/student_summary.csv
	quarto render proposal_report/reports/proposal_report.qmd --to pdf

proposal-report : proposal_report/reports/proposal_report.html proposal_report/reports/proposal_report.pdf


proposal_report/figures/kc_coverage.png proposal_report/figures/kc_coverage_comparison.png \
proposal_report/figures/performance_band.png proposal_report/tables/kc_coverage_comparison_table.csv \
proposal_report/tables/kc_summary.csv proposal_report/tables/missing_assignment.csv \
proposal_report/tables/missing_student_assignment.csv proposal_report/tables/perf_summary.csv \
proposal_report/tables/student_summary.csv: proposal_report/src/eda.py
	python proposal_report/src/eda.py \
		--data_path="data/raw/Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx" \
		--chart_to=proposal_report/figures \
		--table_to=proposal_report/tables


# ===================== FINAL-REPORT ===================== 
proposal_report/final_proposal_report/final_report.html: proposal_report/final_proposal_report/final_report.qmd \
		proposal_report/final_proposal_report/tables/summary_table.csv \
		proposal_report/final_proposal_report/tables/practice_summary.csv
	quarto render proposal_report/final_proposal_report/final_report.qmd --to html
 
proposal_report/final_proposal_report/final_report.pdf: proposal_report/final_proposal_report/final_report.qmd \
		proposal_report/final_proposal_report/tables/summary_table.csv \
		proposal_report/final_proposal_report/tables/practice_summary.csv
	quarto render proposal_report/final_proposal_report/final_report.qmd --to pdf

final-report: proposal_report/final_proposal_report/final_report.html proposal_report/final_proposal_report/final_report.pdf

proposal_report/final_proposal_report/tables/summary_table.csv \
proposal_report/final_proposal_report/tables/practice_summary.csv: data/processed/final_student_kc_data.csv \
		proposal_report/final_proposal_report/src/main.py
	python proposal_report/final_proposal_report/src/main.py \
		--data_path=data/processed/final_student_kc_data.csv \
		--table_to=proposal_report/final_proposal_report/tables \
 

# ===================== CLEAN-ALL =====================
clean-all :
	rm -f data/processed/final_student_kc_data.csv
	rm -f proposal_report/figures/*.png
	rm -f proposal_report/tables/*.csv
	rm -f proposal_report/final_proposal_report/figures/*.png
	rm -f proposal_report/final_proposal_report/tables/*.csv
	rm -f proposal_report/reports/proposal_report.html 
	rm -f proposal_report/reports/proposal_report.pdf
	rm -f proposal_report/final_proposal_report/final_report.pdf
	rm -f proposal_report/final_proposal_report/final_report.html

# ===================== CLEAN-FINAL =====================
clean-final: 
	rm -f proposal_report/final_proposal_report/figures/*.png
	rm -f proposal_report/final_proposal_report/tables/*.csv
	rm -f proposal_report/final_proposal_report/final_report.pdf
	rm -f proposal_report/final_proposal_report/final_report.html

# ===================== CLEAN-PROPOSAL =====================
clean-proposal :
	rm -f proposal_report/figures/*.png
	rm -f proposal_report/tables/*.csv
	rm -f proposal_report/reports/proposal_report.html 
	rm -f proposal_report/reports/proposal_report.pdf