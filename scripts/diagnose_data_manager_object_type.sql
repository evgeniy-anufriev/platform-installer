-- Run with psql using the same database, role and search_path as data-manager.
-- Override the requested names with -v project_name=sdku -v type_name=КР.
\set ON_ERROR_STOP on
\encoding UTF8
\if :{?project_name}
\else
  \set project_name sdku
\endif
\if :{?type_name}
\else
  \set type_name КР
\endif

BEGIN READ ONLY;

SELECT current_database() AS database_name,
       current_user AS database_role,
       inet_server_addr() AS server_address,
       current_setting('search_path') AS search_path,
       to_regclass('project') AS project_table,
       to_regclass('object_type') AS object_type_table,
       to_regclass('public.parameter') AS parameter_table;

SELECT :'project_name' AS requested_project,
       :'type_name' AS requested_type,
       encode(convert_to(:'type_name', 'UTF8'), 'hex') AS requested_type_hex,
       count(*) AS exact_type_matches
FROM object_type AS ot
JOIN project AS pr ON pr.id = ot.project_id
WHERE pr.name = :'project_name' AND ot.name = :'type_name';

-- Include all types in the requested project and the same type name in other projects.
SELECT ot.id AS type_id,
       quote_literal(pr.name) AS project_name,
       quote_literal(ot.name) AS type_name,
       pr.name || ':' || ot.name AS full_name,
       encode(convert_to(pr.name, 'UTF8'), 'hex') AS project_name_hex,
       encode(convert_to(ot.name, 'UTF8'), 'hex') AS type_name_hex,
       counts.parameter_count,
       counts.root_parameter_count
FROM object_type AS ot
JOIN project AS pr ON pr.id = ot.project_id
CROSS JOIN LATERAL (
    SELECT count(*) AS parameter_count,
           count(*) FILTER (WHERE pa.parent IS NULL) AS root_parameter_count
    FROM public.parameter AS pa
    WHERE pa.object_type_id = ot.id
) AS counts
WHERE pr.name = :'project_name' OR ot.name = :'type_name'
ORDER BY pr.name, ot.name, ot.id;

COMMIT;
