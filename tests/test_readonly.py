import pytest

from trino_mcp.readonly import ReadOnlyViolation, validate_read_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  SELECT 1;  ",
        "SHOW CATALOGS",
        "SHOW SCHEMAS FROM hive",
        "DESCRIBE hive.default.foo",
        "EXPLAIN SELECT * FROM foo",
        "WITH t AS (SELECT 1) SELECT * FROM t",
        "VALUES (1, 2), (3, 4)",
        "USE hive.default",
    ],
)
def test_allowed(sql):
    cleaned = validate_read_only(sql)
    assert cleaned
    assert not cleaned.endswith(";")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO foo VALUES (1)",
        "UPDATE foo SET x = 1",
        "DELETE FROM foo",
        "DROP TABLE foo",
        "CREATE TABLE foo (x INT)",
        "ALTER TABLE foo ADD COLUMN y INT",
        "MERGE INTO foo USING bar ON x=y WHEN MATCHED THEN DELETE",
        "CALL system.runtime.kill_query('x')",
        "TRUNCATE TABLE foo",
        "GRANT SELECT ON foo TO bar",
        "REVOKE SELECT ON foo FROM bar",
        "COMMENT ON TABLE foo IS 'x'",
        "SET SESSION optimize_hash_generation = true",
        "SELECT 1; SELECT 2",
        "",
        "   ",
        "SELECT * INTO newtbl FROM oldtbl",
    ],
)
def test_rejected(sql):
    with pytest.raises(ReadOnlyViolation):
        validate_read_only(sql)
