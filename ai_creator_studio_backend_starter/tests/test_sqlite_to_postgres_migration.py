from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "sqlite_to_postgres.py"
spec = importlib.util.spec_from_file_location("sqlite_to_postgres", MODULE_PATH)
migration = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(migration)


def test_export_creates_fk_ordered_portable_bundle(tmp_path):
    db_path = tmp_path / "source.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE parent (parent_id TEXT PRIMARY KEY, label TEXT NOT NULL);
        CREATE TABLE child (child_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id TEXT NOT NULL REFERENCES parent(parent_id), value TEXT);
        CREATE INDEX idx_child_parent ON child(parent_id);
        INSERT INTO parent VALUES ('p1', 'parent');
        INSERT INTO child(parent_id, value) VALUES ('p1', 'child');
    """)
    conn.commit()
    conn.close()

    out = tmp_path / "bundle"
    manifest = migration.export_bundle(db_path, out)
    assert [t["name"] for t in manifest["tables"]] == ["parent", "child"]
    assert manifest["row_count"] == 2
    child = next(t for t in manifest["tables"] if t["name"] == "child")
    assert child["serial_columns"] == ["child_id"]
    data = json.loads((out / child["file"]).read_text().strip())
    assert data == {"child_id": 1, "parent_id": "p1", "value": "child"}
    ddl = (out / "schema.postgresql.sql").read_text()
    assert "BIGSERIAL PRIMARY KEY" in ddl
    assert "AUTOINCREMENT" not in ddl
    assert "REFERENCES parent(parent_id)" in ddl


def test_export_refuses_foreign_key_cycles(tmp_path):
    db_path = tmp_path / "cycle.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE a (id TEXT PRIMARY KEY, b_id TEXT REFERENCES b(id));
        CREATE TABLE b (id TEXT PRIMARY KEY, a_id TEXT REFERENCES a(id));
    """)
    conn.commit()
    conn.close()
    try:
        migration.export_bundle(db_path, tmp_path / "bundle")
    except ValueError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("expected cycle detection")


def test_postgres_ddl_translates_sqlite_storage_types():
    ddl = migration._pg_ddl("CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, raw BLOB, score REAL)")
    assert "BIGSERIAL PRIMARY KEY" in ddl
    assert "BYTEA" in ddl
    assert "DOUBLE PRECISION" in ddl


def test_export_encodes_binary_values_for_jsonl_roundtrip(tmp_path):
    db_path = tmp_path / "binary.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE binary_data (id TEXT PRIMARY KEY, payload BLOB NOT NULL)")
    conn.execute("INSERT INTO binary_data VALUES (?, ?)", ("b1", sqlite3.Binary(b"\\x00\\x01\\xff")))
    conn.commit(); conn.close()
    out = tmp_path / "binary_bundle"
    migration.export_bundle(db_path, out)
    row = json.loads((out / "data/binary_data.jsonl").read_text().strip())
    assert migration._json_restore(row["payload"]) == b"\\x00\\x01\\xff"


def test_export_translates_append_only_triggers_to_postgres(tmp_path):
    db_path = tmp_path / "triggered.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE audit_log (id TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TRIGGER audit_log_no_update
            BEFORE UPDATE ON audit_log
            BEGIN SELECT RAISE(ABORT, 'append-only: don''t edit'); END;
        CREATE TRIGGER audit_log_no_delete
            BEFORE DELETE ON audit_log
            BEGIN SELECT RAISE(ABORT, 'append-only'); END;
        INSERT INTO audit_log VALUES ('a1', 'original');
    """)
    conn.commit(); conn.close()

    out = tmp_path / "bundle"
    manifest = migration.export_bundle(db_path, out)
    assert manifest["trigger_count"] == 2
    assert manifest["triggers"] == ["audit_log_no_delete", "audit_log_no_update"]
    ddl = (out / "schema.postgresql.sql").read_text()
    assert "CREATE FUNCTION acs_raise_append_only_error()" in ddl
    assert "RAISE EXCEPTION USING MESSAGE = TG_ARGV[0]" in ddl
    assert 'CREATE TRIGGER "audit_log_no_delete" BEFORE DELETE ON "audit_log"' in ddl
    assert 'CREATE TRIGGER "audit_log_no_update" BEFORE UPDATE ON "audit_log"' in ddl
    assert "append-only: don''t edit" in ddl
    assert "append-only: don\'\'t edit" in ddl


def test_export_refuses_unsupported_trigger_bodies(tmp_path):
    db_path = tmp_path / "unsupported_trigger.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE source_rows (id TEXT PRIMARY KEY);
        CREATE TABLE audit_rows (id TEXT PRIMARY KEY);
        CREATE TRIGGER copy_after_insert AFTER INSERT ON source_rows
            BEGIN INSERT INTO audit_rows VALUES (NEW.id); END;
    """)
    conn.commit(); conn.close()

    out = tmp_path / "bundle"
    try:
        migration.export_bundle(db_path, out)
    except ValueError as exc:
        assert "trigger copy_after_insert (unsupported trigger body)" in str(exc)
    else:
        raise AssertionError("expected export to refuse unsupported trigger body")
    assert not out.exists()


def test_export_refuses_views_instead_of_silently_omitting_them(tmp_path):
    db_path = tmp_path / "view.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE source_rows (id TEXT PRIMARY KEY);
        CREATE VIEW active_rows AS SELECT id FROM source_rows;
    """)
    conn.commit()
    conn.close()

    try:
        migration.export_bundle(db_path, tmp_path / "bundle")
    except ValueError as exc:
        assert "view active_rows" in str(exc)
    else:
        raise AssertionError("expected export to refuse unsupported view semantics")


def test_export_refuses_virtual_tables(tmp_path):
    db_path = tmp_path / "virtual.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE VIRTUAL TABLE search_index USING fts5(content)")
    conn.commit()
    conn.close()

    try:
        migration.export_bundle(db_path, tmp_path / "bundle")
    except ValueError as exc:
        assert "table search_index" in str(exc)
        assert "does not yet translate" in str(exc)
    else:
        raise AssertionError("expected export to refuse unsupported virtual table semantics")


def test_postgres_sql_splitter_preserves_dollar_quoted_function_body():
    source = """CREATE TABLE sample (id TEXT PRIMARY KEY);
CREATE FUNCTION sample_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION USING MESSAGE = 'one; two';
END;
$$;
CREATE TRIGGER sample_guard BEFORE UPDATE ON sample FOR EACH ROW EXECUTE FUNCTION sample_guard();
"""
    statements = migration._split_sql_statements(source)
    assert len(statements) == 3
    assert "RAISE EXCEPTION USING MESSAGE = 'one; two';" in statements[1]
    assert statements[1].endswith("$$")
    assert statements[2].startswith("CREATE TRIGGER")



def test_postgres_sql_splitter_ignores_semicolons_in_line_and_nested_block_comments():
    source = """-- setup; this semicolon is not a boundary
CREATE TABLE sample (id TEXT); /* outer ; /* nested ; */ still outer ; */
CREATE TABLE second (id TEXT); -- trailing ; comment
"""
    statements = migration._split_sql_statements(source)
    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE sample")
    assert statements[1].startswith("CREATE TABLE second")


def test_postgres_sql_splitter_handles_escape_string_quotes_and_semicolons():
    source = """SELECT E'it\\'s; still one string';
SELECT 'next statement';
"""
    statements = migration._split_sql_statements(source)
    assert len(statements) == 2
    assert "it" in statements[0] and "still one string" in statements[0]
    assert statements[1] == "SELECT 'next statement'"


def test_postgres_sql_splitter_rejects_unterminated_block_comment():
    try:
        migration._split_sql_statements("SELECT 1; /* never closed")
    except ValueError as exc:
        assert "Unterminated block comment" in str(exc)
    else:
        raise AssertionError("expected unterminated block comment to be rejected")

def _make_valid_bundle(tmp_path):
    db_path = tmp_path / "validated.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO records VALUES ('r1', 'safe')")
    conn.commit()
    conn.close()
    bundle = tmp_path / "validated_bundle"
    migration.export_bundle(db_path, bundle)
    return bundle


def test_bundle_preflight_validates_schema_and_data_before_import(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest, schema, payloads = migration._validate_bundle(bundle)
    assert manifest["bundle_version"] == 2
    assert "CREATE TABLE records" in schema
    assert json.loads(payloads["records"].decode().strip()) == {"id": "r1", "value": "safe"}


def test_bundle_preflight_rejects_manifest_path_traversal(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["file"] = "../../outside.jsonl"
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Unexpected data file path" in str(exc)
    else:
        raise AssertionError("expected traversal path rejection")


def test_bundle_preflight_rejects_schema_tampering(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    schema_path = bundle / "schema.postgresql.sql"
    schema_path.write_text(schema_path.read_text() + "-- altered\n")
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Checksum mismatch for schema" in str(exc)
    else:
        raise AssertionError("expected schema checksum rejection")


def test_bundle_preflight_rejects_data_tampering(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    data_path = bundle / "data/records.jsonl"
    data_path.write_text(data_path.read_text().replace("safe", "evil"))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Checksum mismatch for records" in str(exc)
    else:
        raise AssertionError("expected data checksum rejection")


def test_bundle_preflight_rejects_jsonl_column_mismatch_even_with_updated_digest(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    data_path = bundle / "data/records.jsonl"
    data_path.write_text('{"id":"r1","unexpected":"value"}\n')
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["sha256"] = __import__("hashlib").sha256(data_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Column mismatch" in str(exc)
    else:
        raise AssertionError("expected JSONL schema rejection")


def test_bundle_preflight_rejects_symlinked_data_file(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    data_path = bundle / "data/records.jsonl"
    original = data_path.read_bytes()
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(original)
    data_path.unlink()
    data_path.symlink_to(outside)
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Symlink" in str(exc)
    else:
        raise AssertionError("expected symlink rejection")


def test_import_rejects_invalid_bundle_before_loading_postgres_driver(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    schema_path = bundle / "schema.postgresql.sql"
    schema_path.write_text(schema_path.read_text() + "-- tampered\n")
    try:
        migration.import_bundle(bundle, "postgresql://unused")
    except ValueError as exc:
        assert "Checksum mismatch for schema" in str(exc)
    else:
        raise AssertionError("expected bundle preflight to run before PostgreSQL driver import")


def test_bundle_preflight_rejects_legacy_bundle_version(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["bundle_version"] = 1
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "expected 2" in str(exc)
    else:
        raise AssertionError("expected legacy bundle version rejection")


def test_bundle_preflight_rejects_boolean_manifest_counts(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["row_count"] = True
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "row_count is invalid" in str(exc)
    else:
        raise AssertionError("expected boolean row_count rejection")


def test_bundle_preflight_rejects_trigger_inventory_drift(tmp_path):
    db_path = tmp_path / "triggered.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE audit_log (id TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'append-only'); END;
    """)
    conn.commit(); conn.close()
    bundle = tmp_path / "trigger_bundle"
    migration.export_bundle(db_path, bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["triggers"] = []
    manifest["trigger_count"] = 0
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "trigger inventory does not match" in str(exc)
    else:
        raise AssertionError("expected trigger inventory mismatch rejection")


def test_bundle_preflight_rejects_duplicate_trigger_inventory(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["triggers"] = ["duplicate", "duplicate"]
    manifest["trigger_count"] = 2
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "trigger inventory is inconsistent" in str(exc)
    else:
        raise AssertionError("expected duplicate trigger inventory rejection")


def test_bundle_preflight_rejects_duplicate_serial_columns(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["serial_columns"] = ["id", "id"]
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Invalid serial_columns" in str(exc)
    else:
        raise AssertionError("expected duplicate serial column rejection")


def test_schema_trigger_inventory_ignores_trigger_text_inside_function_body_and_literals():
    schema = '''CREATE FUNCTION sample_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION USING MESSAGE = 'CREATE TRIGGER "fake_trigger";';
END;
$$;
CREATE TRIGGER "real_trigger" BEFORE UPDATE ON "records"
FOR EACH ROW EXECUTE FUNCTION sample_guard();
'''
    assert migration._schema_trigger_names(schema) == ["real_trigger"]


def test_schema_trigger_inventory_rejects_duplicate_declarations():
    schema = '''CREATE TRIGGER "same_name" BEFORE UPDATE ON "records" FOR EACH ROW EXECUTE FUNCTION guard();
CREATE TRIGGER "same_name" BEFORE DELETE ON "records" FOR EACH ROW EXECUTE FUNCTION guard();
'''
    assert migration._schema_trigger_names(schema) == ["same_name", "same_name"]


def test_bundle_preflight_rejects_unmanifested_files(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    (bundle / "data" / "unlisted.jsonl").write_text('{"unexpected":true}\n')
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "file set mismatch" in str(exc)
        assert "unlisted.jsonl" in str(exc)
    else:
        raise AssertionError("expected unmanifested data file rejection")


def test_bundle_preflight_rejects_duplicate_jsonl_object_keys(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    data_path = bundle / "data/records.jsonl"
    data_path.write_text('{"id":"r1","id":"r2","value":"safe"}\n')
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["sha256"] = __import__("hashlib").sha256(data_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Duplicate JSON object key" in str(exc)
    else:
        raise AssertionError("expected duplicate JSON key rejection")


def test_bundle_preflight_rejects_nonstandard_json_numbers(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    data_path = bundle / "data/records.jsonl"
    data_path.write_text('{"id":"r1","value":NaN}\n')
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"][0]["sha256"] = __import__("hashlib").sha256(data_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Non-standard JSON numeric constant" in str(exc)
    else:
        raise AssertionError("expected non-standard JSON number rejection")


def test_bundle_preflight_rejects_duplicate_manifest_keys(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    raw = manifest_path.read_text()
    manifest_path.write_text(raw.rstrip()[:-1] + ',"row_count":999}')
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Duplicate JSON object key" in str(exc)
    else:
        raise AssertionError("expected duplicate manifest key rejection")


def test_json_restore_rejects_malformed_binary_payloads():
    for value in (123, "not-base64!"):
        try:
            migration._json_restore({"__acs_bytes_b64__": value})
        except ValueError:
            pass
        else:
            raise AssertionError("expected malformed binary payload rejection")


def test_schema_trigger_inventory_ignores_comment_text():
    schema = '''-- CREATE TRIGGER \"fake_trigger\" BEFORE UPDATE ON \"records\";\nCREATE TABLE records (id TEXT);\n'''
    assert migration._schema_trigger_names(schema) == []


def test_bundle_preflight_rejects_symlinked_data_directory(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    original = bundle / "data"
    outside = tmp_path / "outside_data"
    outside.mkdir()
    (outside / "records.jsonl").write_bytes((original / "records.jsonl").read_bytes())
    original.rename(bundle / "data_original")
    original.symlink_to(outside, target_is_directory=True)
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "Symlink" in str(exc)
    else:
        raise AssertionError("expected symlinked data directory rejection")


def test_bundle_preflight_rejects_unexpected_empty_directories(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    (bundle / "unlisted_empty_directory").mkdir()
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "unexpected_directories" in str(exc)
        assert "unlisted_empty_directory" in str(exc)
    else:
        raise AssertionError("expected unmanifested directory rejection")


def test_bundle_preflight_preserves_unicode_line_separators_inside_json_strings(tmp_path):
    db_path = tmp_path / "unicode_separators.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
    value = "before\u2028line\u2029paragraph\u0085next\u000bvertical"
    conn.execute("INSERT INTO records VALUES (?, ?)", ("r1", value))
    conn.commit(); conn.close()

    bundle = tmp_path / "unicode_bundle"
    migration.export_bundle(db_path, bundle)
    manifest, _schema, payloads = migration._validate_bundle(bundle)
    record = json.loads(payloads["records"].decode("utf-8").strip())
    assert record["value"] == value
    assert manifest["row_count"] == 1


def test_export_refuses_nonempty_destination_to_prevent_stale_bundle_files(tmp_path):
    db_path = tmp_path / "source.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY)")
    conn.commit(); conn.close()
    destination = tmp_path / "existing_bundle"
    destination.mkdir()
    (destination / "stale.jsonl").write_text('{"unrelated":true}\n')

    try:
        migration.export_bundle(db_path, destination)
    except ValueError as exc:
        assert "destination is not empty" in str(exc)
    else:
        raise AssertionError("expected export to refuse nonempty destination")
    assert (destination / "stale.jsonl").exists()
    assert not (destination / "manifest.json").exists()


def test_bundle_preflight_rejects_float_bundle_version(tmp_path):
    bundle = _make_valid_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["bundle_version"] = 2.0
    manifest_path.write_text(json.dumps(manifest))
    try:
        migration._validate_bundle(bundle)
    except ValueError as exc:
        assert "as an integer" in str(exc)
    else:
        raise AssertionError("expected non-integer bundle version rejection")


def test_export_rejects_non_finite_real_values_as_non_json_data(tmp_path):
    db_path = tmp_path / "nonfinite.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE measurements (id TEXT PRIMARY KEY, value REAL)")
    conn.execute("INSERT INTO measurements VALUES (?, ?)", ("m1", float("inf")))
    conn.commit(); conn.close()
    try:
        migration.export_bundle(db_path, tmp_path / "nonfinite_bundle")
    except ValueError as exc:
        assert "Out of range float values" in str(exc)
    else:
        raise AssertionError("expected non-finite JSON number rejection")
    assert not (tmp_path / "nonfinite_bundle").exists(), "failed export must not publish a partial bundle"
    assert not list(tmp_path.glob(".nonfinite_bundle.staging-*")), "failed export must clean staging data"


def test_export_atomically_replaces_an_existing_empty_destination(tmp_path):
    db_path = tmp_path / "atomic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO records VALUES ('r1')")
    conn.commit(); conn.close()
    destination = tmp_path / "bundle"
    destination.mkdir()

    manifest = migration.export_bundle(db_path, destination)
    assert manifest["row_count"] == 1
    checked, _schema, payloads = migration._validate_bundle(destination)
    assert checked["row_count"] == 1
    assert json.loads(payloads["records"].decode().strip()) == {"id": "r1"}
    assert not list(tmp_path.glob(".bundle.staging-*"))


def test_export_rejects_symlink_destination_without_touching_target(tmp_path):
    db_path = tmp_path / "source.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY)")
    conn.commit(); conn.close()
    target = tmp_path / "real_destination"
    target.mkdir()
    link = tmp_path / "bundle_link"
    link.symlink_to(target, target_is_directory=True)
    try:
        migration.export_bundle(db_path, link)
    except ValueError as exc:
        assert "must not be a symlink" in str(exc)
    else:
        raise AssertionError("expected symlink destination rejection")
    assert list(target.iterdir()) == []
