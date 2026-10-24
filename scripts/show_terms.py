#!/usr/bin/env python3
"""Read-only peek at catalog.dataset_info, terms, and term counts."""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

url = URL.create("postgresql+psycopg2",
    username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT") or 5432),
    database=os.environ.get("DB_NAME") or "hackathon")
engine = create_engine(url, connect_args={"sslmode": "require", "connect_timeout": 10})

def show(conn, title, q, n=30):
    print(f"\n== {title}")
    for i, r in enumerate(conn.execute(text(q))):
        if i >= n: break
        print("  ", dict(r._mapping))

with engine.connect() as c:
    show(c, "dataset_info", "SELECT * FROM catalog.dataset_info")
    show(c, "terms", "SELECT * FROM catalog.terms ORDER BY begin_date DESC")
    show(c, "courses per term/career",
         "SELECT term_code, academic_career, count(*) FROM catalog.courses GROUP BY 1,2 ORDER BY 1 DESC")
    show(c, "sample courses", "SELECT course_key, term_code, display_code, title, units_minimum, units_maximum "
                              "FROM catalog.courses LIMIT 5")
    show(c, "sample sections", "SELECT section_key, course_key, section, credits, section_type, instruction_type "
                               "FROM catalog.sections LIMIT 5")
    show(c, "sample meetings", "SELECT * FROM catalog.meetings LIMIT 5")
    show(c, "building codes in use",
         "SELECT building_code, building, count(*) FROM catalog.meetings GROUP BY 1,2 ORDER BY 3 DESC", 60)
    show(c, "section_type / instruction_type values",
         "SELECT section_type, instruction_type, count(*) FROM catalog.sections GROUP BY 1,2 ORDER BY 3 DESC", 20)