import json
import pandas as pd

with open("test_data.txt", encoding="utf-8") as f:
    text = f.read().strip()

try:
    chunks = [json.loads(text)]                       # 파일 전체가 JSON 1개
except json.JSONDecodeError:
    chunks = [json.loads(l) for l in text.splitlines() if l.strip()]   # 줄마다 JSON 1개

rows = []
for c in chunks:
    rows.extend(c["data"])

df = pd.DataFrame(rows)
df["KEY"] = df["KEY"].astype(int)
df.to_csv("test_data.csv", index=False, encoding="utf-8")
print(df.shape)