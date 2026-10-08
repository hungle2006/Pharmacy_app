-- Illustration only. Edit identifiers to match the existing DAV table and verify price units.
-- Assumes dav_products(id, drug_name, ingredient, strength, dosage_form,
-- manufacturer, country, unit_price_vnd, price_type, therapeutic_group,
-- updated_at, registration_no)
CREATE OR REPLACE VIEW analytics_drug_prices AS
SELECT id::text AS id, drug_name::text AS drug_name,
 ingredient::text AS ingredient, strength::text AS strength,
 dosage_form::text AS dosage_form, manufacturer::text AS manufacturer,
 country::text AS country, unit_price_vnd::numeric AS price_vnd,
 price_type::text AS price_type, therapeutic_group::text AS therapeutic_group,
 updated_at::date AS snapshot_date, registration_no::text AS registration_no
FROM dav_products WHERE unit_price_vnd IS NOT NULL AND unit_price_vnd >= 0;
-- Grant SELECT on the view only to the application DB role.
