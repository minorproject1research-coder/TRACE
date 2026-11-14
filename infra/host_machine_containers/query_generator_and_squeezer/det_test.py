import hashlib, json, urllib.request

URL = "http://127.0.0.1:8001/v1/completions"
Q = "How does retrieval-augmented generation constrain the creativity and diversity of large language models?"
PROMPT = f"<|im_start|>user\n{Q}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

def complete(model, **kw):
    body = {"model": model, "prompt": PROMPT, "max_tokens": 600, **kw}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["text"]

def first_diff(a, b):
    return next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))

def trial(label, model, runs=4, **kw):
    outs = [complete(model, **kw) for _ in range(runs)]
    hashes = [hashlib.md5(o.encode()).hexdigest()[:8] for o in outs]
    same = len(set(outs)) == 1
    print(f"{model:8s} {label:22s} identical={same} hashes={hashes}"
          + ("" if same else f" first_diff_at_char={first_diff(outs[0], outs[1])}"))

for model in ("planner", "judge"):
    complete(model, temperature=0)                     # warm-up, so the first call is not special
    trial("temperature=0", model, temperature=0)
    trial("temp=0.8 seed=7", model, temperature=0.8, seed=7)
    trial("temp=0.8 no seed", model, temperature=0.8)  # control: this one SHOULD differ