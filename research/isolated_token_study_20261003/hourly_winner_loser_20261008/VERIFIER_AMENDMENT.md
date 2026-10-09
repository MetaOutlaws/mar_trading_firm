# Verification-only correction

The frozen verify_report.py failed its first independent candidate-count check because default CSV float parsing rounded ten candidate median comparisons across the exact equality boundary. The stored Parquet features,JSON nomination,trade calculations and CSV text were correct. Reading CSV with float_precision=round_trip restores the exact floats. verify_report_v2.py changes only CSV parsing in the verifier;the original remains unchanged. No treatment outputs or nomination were rerun or modified.
