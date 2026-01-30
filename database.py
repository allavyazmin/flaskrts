import sqlite3

integrity_error = sqlite3.IntegrityError

def executedb(sql: str, parameters: tuple | None = None, all: bool = False):
    with sqlite3.connect("database.db") as db:
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        if not parameters:
            cur.execute(sql)
        else:
            cur.execute(sql, parameters or ())
        if all:
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        row = cur.fetchone()
        return dict(row) if row is not None else None

def make_table(title: str, data: dict):
    types = ",".join(" ".join((k, v)) for k, v in data.items())
    try:
        executedb(f"CREATE TABLE IF NOT EXISTS {title} ({types})")
        return None
    except Exception as e:
        print(e)
        return e