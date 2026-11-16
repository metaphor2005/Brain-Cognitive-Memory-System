import json
import sys

sys.path.insert(0, ".")
from api.server import app  # noqa: E402

client = app.test_client()
res = client.get("/api/memory/universe?space_id=jiangyan&limit=2000")
print("status", res.status_code)
data = res.get_json()
print("ok", data.get("ok"))
print("stats", json.dumps(data.get("stats"), ensure_ascii=False))
print("core", json.dumps(data.get("core"), ensure_ascii=False)[:180])
for key in ("beliefs", "topics", "experiences", "entities", "changes", "moods", "affection"):
    print(key, len(data.get(key) or []))
print("sample_belief", json.dumps((data.get("beliefs") or [{}])[0], ensure_ascii=False)[:240])
print("sample_topic", json.dumps((data.get("topics") or [{}])[0], ensure_ascii=False)[:240])
