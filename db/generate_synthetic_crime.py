"""Appends SYNTHETIC (randomly generated) crime_daily rows to seed.sql, for
every district x every day in the range below. Numbers are made up -- not
real crime statistics -- so local dev/testing has realistic-looking report
data without ever putting actual crime figures in git history.

Usage: python generate_synthetic_crime.py
(Run once after schema.sql + the divisions/districts insert in seed.sql
already exist; this appends to seed.sql.)
"""
import random
from datetime import date, timedelta

START = date(2026, 5, 1)
END = date(2026, 8, 20)

# The 41 district ids seeded in seed.sql above this script's output. Not a
# contiguous 1..41 range (district ids follow the real table's numbering),
# so this list is read back out of seed.sql rather than assumed.
def _load_district_ids():
    ids = []
    with open("seed.sql", encoding="utf-8") as f:
        for line in f:
            if line.startswith("INSERT INTO districts"):
                ids.append(int(line.split("VALUES (", 1)[1].split(",", 1)[0]))
    return ids


DISTRICT_IDS = _load_district_ids()

# Rough per-day Poisson rate per category, loosely shaped after real report
# output magnitudes seen this project (murder/rape rare, robbery/snatching
# more common). Purely for making synthetic reports look plausible.
CATEGORY_RATES = {
    "murder": 0.15,
    "dacoity": 0.05,
    "robbery": 0.6,
    "dacoity_robbery_murder": 0.02,
    "dacoity_robbery_injury": 0.03,
    "dacoity_robbery_rape": 0.005,
    "snatching_jhappata": 0.5,
    "child_abuse": 0.1,
    "rape": 0.08,
    "gang_rape": 0.03,
    "sodomy": 0.03,
    "road_accident_casualties": 0.4,
    "acid_attack": 0.02,
    "religious_issues": 0.02,
}


def poisson(lam, rng):
    """Knuth's algorithm -- no numpy dependency needed for small lambda."""
    if lam <= 0:
        return 0
    l_val = 2.718281828459045 ** -lam
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= l_val:
            return k - 1


def main():
    rng = random.Random(42)  # fixed seed: reproducible synthetic data
    district_factor = {d: rng.uniform(0.4, 1.8) for d in DISTRICT_IDS}

    lines = ["\n-- crime_daily (SYNTHETIC data, not real crime statistics)\n"]
    cols = ["report_date", "district_id"] + list(CATEGORY_RATES.keys())
    col_list = ", ".join(cols)

    day = START
    n = 0
    while day <= END:
        for d in DISTRICT_IDS:
            factor = district_factor[d]
            vals = [f"'{day.isoformat()}'", str(d)]
            for cat, rate in CATEGORY_RATES.items():
                vals.append(str(poisson(rate * factor, rng)))
            lines.append(f"INSERT INTO crime_daily ({col_list}) VALUES ({', '.join(vals)});")
            n += 1
        day += timedelta(days=1)

    with open("seed.sql", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Appended {n} synthetic crime_daily rows to seed.sql")


if __name__ == "__main__":
    main()
