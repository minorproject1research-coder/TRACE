import time
from apps.api.services.llm_service import squeezer_json

for i in range(3):
    t = time.time()
    squeezer_json('Return ONLY JSON: {"ok": true}')
    print(f"call {i + 1}: {time.time() - t:.1f}s")