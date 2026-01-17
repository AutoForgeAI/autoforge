from autocoder.core.database import Database


def test_regression_selection_least_tested(tmp_path):
    db = Database(str(tmp_path / "agent_system.db"))

    f1 = db.create_feature("feat-1", "desc-1", "backend")
    f2 = db.create_feature("feat-2", "desc-2", "backend")
    f3 = db.create_feature("feat-3", "desc-3", "backend")

    for fid in (f1, f2, f3):
        assert db.mark_feature_passing(fid) is True

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE features SET regression_count = 5 WHERE id = ?", (f1,))
        cur.execute("UPDATE features SET regression_count = 1 WHERE id = ?", (f2,))
        cur.execute("UPDATE features SET regression_count = NULL WHERE id = ?", (f3,))
        conn.commit()

    rows = db.get_passing_features_for_regression(limit=2)
    assert [r["id"] for r in rows] == [f3, f2]

    assert int(db.get_feature(f3)["regression_count"] or 0) == 1
    assert int(db.get_feature(f2)["regression_count"] or 0) == 2
    assert int(db.get_feature(f1)["regression_count"] or 0) == 5
