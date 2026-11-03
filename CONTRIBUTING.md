# Contributing

- Never commit `.env`, API secrets, private user data, raw user uploads, or unlicensed raster files.
- Keep raw observed targets distinct from imputed features and model outputs.
- Add a source citation, license note, units, time window, spatial resolution, and quality flags for each new connector.
- Add tests for date windows, units, boundary handling, and train/test time separation.
- Do not report accuracy as a single percentage. Report MAE/RMSE, OOF rows, time folds, and Persistence comparison.
