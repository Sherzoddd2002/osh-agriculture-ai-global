# MVP data dictionary

## User yield CSV (one crop-year row)

- `year`: harvest/target year.
- `yield_t_ha`: observed yield in tonnes/hectare.
- `area_ha`: optional area in hectares.
- `production_t`: optional production in tonnes.
- Dataset metadata records `area_basis` so sown-area and harvested-area yield definitions are not silently mixed.

## NASA POWER season features

- `wx_t2m_mean_c`, `wx_tmax_mean_c`, `wx_tmin_mean_c`
- `wx_precip_sum_mm`, `wx_rh_mean_pct`, `wx_wind_mean_m_s`
- `wx_solar_mean_mj_m2_day`, `wx_hot_days_ge_35c`, `wx_frost_days_lt_0c`
- `wx_gdd_base5_cday`, `wx_observed_days`, `wx_expected_days`, `wx_coverage_pct`

Weather aggregates use the user-declared season dates. For a winter crop, a season such as `10-01` to `06-30` crosses calendar years and is keyed by harvest year. Missing daily values remain missing; coverage is retained.

## Status vocabularies

- Yield target: `OBSERVED` only in the MVP uploader.
- Future additions: `IMPUTED_FEATURE`, `HINDCAST`, `FORECAST`, `UNAVAILABLE`.
- Source status: `AVAILABLE`, `NO_DATA`, `NOT_CONFIGURED`, `FAILED`, `PARTIAL`.
