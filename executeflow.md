# CLEAN
Remove-Item .\output\*.csv -Force -ErrorAction SilentlyContinue
Remove-Item .\output\cxo\*.csv -Force -ErrorAction SilentlyContinue
Remove-Item .\output\final\*.csv -Force -ErrorAction SilentlyContinue

# PHASE 1
python phase1_input_validation.py

# PHASE 2
python phase2_discovery.py

# PHASE 3
python scraper.py

# PHASE 4
python phase4_cxo.py

# PHASE 5
python phase5_validation.py

# PHASE 5.1
python phase5_1_enrichment.py

# PHASE 6
python phase6_final_export.py

# PHASE 6.1
python phase6_1_contact_merge.py
