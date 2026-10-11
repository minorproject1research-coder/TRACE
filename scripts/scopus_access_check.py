"""Check what a Scopus API key can access from the machine / network it runs on.

Standard library only (no pip install). Run it on the campus network (or VPN) of an institution that subscribes to
Scopus, with an Elsevier API key from https://dev.elsevier.com :

    python scopus_access_check.py YOUR_API_KEY
    python scopus_access_check.py YOUR_API_KEY --insttoken YOUR_INSTITUTIONAL_TOKEN     # optional
    (or set the SCOPUS_API_KEY / SCOPUS_INSTTOKEN environment variables instead of passing them)

It prints one result per check and a verdict. The key is never printed in full. Send the whole output back.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SEARCH = "https://api.elsevier.com/content/search/scopus"
ABSTRACT_BY_DOI = "https://api.elsevier.com/content/abstract/doi/"
QUERY = 'TITLE-ABS-KEY("speculative decoding" AND "inference latency") AND PUBYEAR > 2022'
TEST_DOI = "10.18653/v1/2024.findings-acl.456"


def call(url, params, key, insttoken):
    headers = {"X-ELS-APIKey": key, "Accept": "application/json"}
    if insttoken:
        headers["X-ELS-Insttoken"] = insttoken
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return e.code, dict(e.headers), body
    except Exception as e:                                  # no network, DNS, TLS ...
        return None, {}, f"{type(e).__name__}: {e}"


def header(headers, name):
    for k, v in headers.items():
        if k.lower() == name:
            return v
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", nargs="?", default=os.getenv("SCOPUS_API_KEY", ""))
    ap.add_argument("--insttoken", default=os.getenv("SCOPUS_INSTTOKEN", ""))
    args = ap.parse_args()
    if not args.key:
        sys.exit("Give the API key as an argument or set SCOPUS_API_KEY.")
    key, tok = args.key.strip(), args.insttoken.strip()
    print(f"key: {key[:4]}...{key[-4:]} (length {len(key)}) | institutional token: {'yes' if tok else 'no'}")
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
            print("public IP of this network:", r.read().decode())
    except Exception:
        print("public IP of this network: (could not look up)")

    results = {}

    # 1. STANDARD search
    status, h, body = call(SEARCH, {"query": QUERY, "view": "STANDARD", "count": 5}, key, tok)
    results["standard"] = status == 200
    print(f"\n[1] Search, STANDARD view -> HTTP {status} | {header(h, 'x-els-status')[:80]}")
    print(f"    quota: limit {header(h, 'x-ratelimit-limit')}, remaining {header(h, 'x-ratelimit-remaining')}")
    if status == 200:
        sr = body["search-results"]
        print("    total results:", sr.get("opensearch:totalResults"))
        for e in sr.get("entry", [])[:3]:
            print("    -", (e.get("dc:title") or "")[:70], "| cited", e.get("citedby-count"), "| type", e.get("subtype"))
    else:
        print("    ", str(body)[:300])

    # 2. COMPLETE search (abstract + full author list)
    status, h, body = call(SEARCH, {"query": QUERY, "view": "COMPLETE", "count": 5}, key, tok)
    print(f"\n[2] Search, COMPLETE view (abstract, all authors, keywords) -> HTTP {status} | {header(h, 'x-els-status')[:80]}")
    got_abstract = False
    if status == 200:
        entries = body["search-results"].get("entry", [])
        got_abstract = any(e.get("dc:description") for e in entries)
        for e in entries[:3]:
            print("    -", (e.get("dc:title") or "")[:60], "| abstract chars", len(e.get("dc:description") or ""),
                  "| authors", len(e.get("author") or []), "| keywords", bool(e.get("authkeywords")))
    else:
        print("    ", str(body)[:300])
    results["complete"] = status == 200 and got_abstract

    # 3. Abstract Retrieval by DOI
    status, h, body = call(ABSTRACT_BY_DOI + TEST_DOI, {"view": "META_ABS"}, key, tok)
    print(f"\n[3] Abstract Retrieval by DOI, META_ABS view -> HTTP {status} | {header(h, 'x-els-status')[:80]}")
    ok_abs = False
    if status == 200:
        core = body.get("abstracts-retrieval-response", {}).get("coredata", {})
        ok_abs = bool(core.get("dc:description"))
        print("    abstract chars:", len(core.get("dc:description") or ""))
    else:
        print("    ", str(body)[:300])
    results["abstract_retrieval"] = ok_abs

    print("\n=== VERDICT ===")
    if results["complete"] or results["abstract_retrieval"]:
        print("GOOD: this key/network can read abstracts. Scopus can be used as a retrieval source.")
    elif results["standard"]:
        print("LIMITED: search works (titles, DOI, venue, citation count) but abstracts are NOT available "
              "(COMPLETE / META_ABS refused). Try again from the campus network or with an institutional token.")
    else:
        print("NO ACCESS: even the basic search failed. Check the key, or the network / firewall.")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
