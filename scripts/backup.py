"""Safe online backup of SOCHI SHOW's own SQLite only; does not access JACKSIDE."""
import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--database', default='./data/sochi.sqlite3')
p.add_argument('--media', default='./data/media')
p.add_argument('--out', default='./backups')
a = p.parse_args()
db = Path(a.database)
if not db.is_file():
    raise SystemExit(f'Database is missing: {db}')
target = Path(a.out) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
target.mkdir(parents=True, exist_ok=False)
with sqlite3.connect(str(db)) as origin, sqlite3.connect(str(target / db.name)) as dest:
    origin.backup(dest)
if Path(a.media).is_dir():
    shutil.copytree(a.media, target / 'media')
print(target.resolve())
