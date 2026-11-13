"""Lightweight shared feature schema: identical in training and Render inference."""
HORIZONS=(3,6,12)
# No fixed-day target matching. Market labels use all filing events in complete
# calendar windows; no-event windows stay unobserved/censored.
CATEGORICAL=["ingredient","strength","dosage_form","manufacturer",
             "country","package","price_type","unit"]
NUMERIC=["log_last_price","previous_change","days_since_previous",
         "origin_year","origin_month","horizon_months"]
FEATURES=CATEGORICAL+NUMERIC
