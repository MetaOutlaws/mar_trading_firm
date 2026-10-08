# Attempt record

preflight_v1 stopped on the BTC raw-input SHA256 check before any path or delayed outcome scoring. The local restored BTC file was incomplete (35,651,584 bytes; SHA256 4ab5184b8b19bcb0497134ef3d1a0c673ef0d7360080f69a729fb119ebefbd35). The verified original ZIP member is 87,559,641 bytes and matches the frozen a6d3cf242680123f4bc3ca16cf88009d0567d5db65ab770270d98d6d6a9c7aa0 digest. Restored that exact member, preserved the incomplete local file and failure log, and reran preflight_v2. No source data content was recalculated or altered. Cause of incomplete local extraction is unestablished. Remaining five raw files matched frozen hashes.

The transient environment lacked pyarrow/pytest. Installed pyarrow25.0.1 and pytest9.1.1 in a task-local environment; packages are captured in freeze.json. No existing runtime repository or frozen sources were changed.

preflight_v2 passed all138 baseline raw/130 admitted cost rows. Protocol commit4d1792891682b7570ee1c3a799defb988b1df72a and10 exact file readbacks preceded scoring. results_v1 completed without treatment failure. Independent report verification passed576 rows/156 intervals.
