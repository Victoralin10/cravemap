"""Check minimo: python3 agent/test_agent.py"""
import os

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TABLE_NAME", "dummy")

from agent import pick_ids

valid = {"ceviche-01": 1, "lomo-02": 1, "anticucho-03": 1, "causa-04": 1}

assert pick_ids("lomo-02\nceviche-01\nanticucho-03", valid) == ["lomo-02", "ceviche-01", "anticucho-03"]
assert pick_ids("- ceviche-01\n2. lomo-02", valid) == ["ceviche-01", "lomo-02"], "limpia vinetas y numeracion"
assert pick_ids("ceviche-01\nceviche-01\nlomo-02", valid) == ["ceviche-01", "lomo-02"], "sin repetidos"
assert pick_ids("pizza-99\nno existe", valid) == [], "descarta ids inventados"
assert pick_ids("a\nb\nc\nd", {"a":1,"b":1,"c":1,"d":1}) == ["a","b","c"], "corta en 3"
assert pick_ids("", valid) == []
assert pick_ids("ceviche-01", valid) == ["ceviche-01"], "no mutila el sufijo numerico del id"
print("ok")
