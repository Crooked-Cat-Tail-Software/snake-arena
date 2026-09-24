-- Runs automatically the first time the `db` service's data volume is
-- created (Postgres only runs scripts in /docker-entrypoint-initdb.d on a
-- fresh, empty data directory -- not on every restart). POSTGRES_DB (see
-- docker-compose.yml) creates the main app database; this adds a second,
-- separate database for the automated test suite, so running `pytest`
-- never touches -- or gets confused with -- data from a real run of the app.
CREATE DATABASE snake_arena_test;
