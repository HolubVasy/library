-- Fast substring search over carrier names and paths (ILIKE '%...%'), for finding a file by any of its names.
create extension if not exists pg_trgm;
create index if not exists carrier_file_location_trgm on carrier_file using gin (location gin_trgm_ops);
