"""Create local fixture files used by HEAAL E2 tasks.

Every HEAAL E2 run starts by invoking this script. It writes the input
files to a well-known directory (/tmp/heaal_e2_data/) so the task
prompts can reference stable paths. Idempotent: re-running overwrites
the fixtures back to canonical content.

Corresponding output directory /tmp/heaal_e2_out/ is created empty
(for tasks that write output files).
"""
from __future__ import annotations

import shutil
from pathlib import Path

DATA = Path("/tmp/heaal_e2_data")
OUT = Path("/tmp/heaal_e2_out")

FIXTURES = {
    # 12 integers, known sum = 78
    "numbers.txt": "\n".join("1 2 3 4 5 6 7 8 9 10 11 12".split()) + "\n",

    # 10 reviews — 6 positive, 4 negative (by manual labelling)
    "reviews.txt": (
        "This movie was absolutely fantastic, I loved every minute.\n"
        "Terrible experience, would not recommend to anyone.\n"
        "Great value for money, exceeded my expectations.\n"
        "Waste of time and money, very disappointed.\n"
        "Highly recommended, the best I have ever tried.\n"
        "Complete garbage, stay away.\n"
        "Wonderful service and excellent quality.\n"
        "Mediocre at best, nothing special about it.\n"
        "Outstanding product, worth every penny.\n"
        "Shipping was too slow and packaging was damaged.\n"
    ),

    # 12 log lines tagged with severity levels in the content
    "log.txt": (
        "2026-04-22 10:15:03 INFO: Application started successfully\n"
        "2026-04-22 10:15:04 INFO: Database connection established\n"
        "2026-04-22 10:16:12 WARN: Slow query detected (1.2s)\n"
        "2026-04-22 10:17:45 ERROR: Failed to fetch user profile\n"
        "2026-04-22 10:18:01 INFO: Cache warmed up\n"
        "2026-04-22 10:18:30 WARN: Retry limit approaching\n"
        "2026-04-22 10:19:15 ERROR: Payment gateway timeout\n"
        "2026-04-22 10:19:20 INFO: Fallback activated\n"
        "2026-04-22 10:20:00 ERROR: Disk write failure on /var/data\n"
        "2026-04-22 10:20:45 WARN: Memory usage at 87%\n"
        "2026-04-22 10:21:00 INFO: Background job completed\n"
        "2026-04-22 10:21:30 INFO: Metrics flushed\n"
    ),

    # 8 book titles, mixed genres
    "books.txt": (
        "The Pragmatic Programmer\n"
        "Pride and Prejudice\n"
        "A Brief History of Time\n"
        "Dune\n"
        "Clean Code\n"
        "The Great Gatsby\n"
        "Sapiens: A Brief History of Humankind\n"
        "Neuromancer\n"
    ),
}


def main() -> int:
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    for name, body in FIXTURES.items():
        (DATA / name).write_text(body, encoding="utf-8")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # Verification summary
    for name in FIXTURES:
        p = DATA / name
        print(f"  wrote {p}  ({p.stat().st_size} bytes)")
    print(f"  output dir ready: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
