-- Bootstrap two databases: app + orthanc.
-- Postgres `postgres` superuser runs this on first start.

CREATE DATABASE app;
CREATE DATABASE orthanc;

-- TODO (production): create a database trigger that blocks
-- UPDATE/DELETE on `audit_events` to make the audit log
-- append-only at the storage layer. The application layer already
-- avoids mutation, but a defense-in-depth trigger should exist
-- before production deployment. Example:
--
--   CREATE FUNCTION audit_immutable() RETURNS trigger AS $$
--   BEGIN RAISE EXCEPTION 'audit_events is append-only'; END;
--   $$ LANGUAGE plpgsql;
--   CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events
--     FOR EACH ROW EXECUTE FUNCTION audit_immutable();
