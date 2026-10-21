"""Lightweight shared feature schema: identical in training and Render inference."""
HORIZONS=(3,6,12)
TARGET_DAYS={3:91,6:183,12:365}
TOLERANCES={3:35,6:50,12:50}
CATEGORICAL=["ingredient","strength","dosage_form","manufacturer",
             "country","package","price_type","unit"]
NUMERIC=["log_last_price","previous_change","days_since_previous",
         "origin_year","origin_month","horizon_months"]
FEATURES=CATEGORICAL+NUMERIC
