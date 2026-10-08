-- PharmaBiz read-only schema audit: run in Neon SQL Editor.
-- Never run destructive migrations until a backup and source model are reviewed.
-- Database: neondb, schema: public

-- 1. Columns and data types for all 8 relevant tables.
SELECT table_name, ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('dav_product','price_record','dav_rxnorm_mapping','disease',
                     'medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component')
ORDER BY table_name, ordinal_position;

-- 2. Approximate table sizes (planner estimates, not exact COUNT).
SELECT c.relname AS table_name,
       c.reltuples::bigint AS estimated_rows
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind IN ('r','p')
  AND c.relname IN ('dav_product','price_record','dav_rxnorm_mapping','disease',
                    'medi_relation','rxnorm_concept','rxnorm_scd','rxnorm_scd_component')
ORDER BY c.relname;

-- 3. Existing foreign key relationships.
SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name,
       ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name=kcu.constraint_name
 AND tc.table_schema=kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name=ccu.constraint_name
 AND tc.table_schema=ccu.table_schema
WHERE tc.constraint_type='FOREIGN KEY'
  AND tc.table_schema='public'
ORDER BY tc.table_name,kcu.column_name;

-- 4. Examine small product sample without fetching user/patient data.
SELECT dav_row_id,registration_number,drug_name,active_ingredient_raw,strength_raw
FROM public.dav_product ORDER BY dav_row_id LIMIT 15;
