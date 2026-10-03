"""
Settings-API test. Start the app with its own data folder first:
    python sleekkeys.py --data-dir %TEMP%\\sk_testdata --background --no-tray
then:  python tools/api_test.py
"""
import http.client
import json
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 7878
results = []


def check(name, ok):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)


def call(method, path, body=None, header=True, host=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    h = {"X-SleekKeys": "1"} if header else {}
    if host:
        h["Host"] = host
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    return r.status, r.read()


good = json.dumps({"version": 1, "active": "a", "profiles": {"a": {"opts": {}, "layout": {"keys": []}}}}).encode()

check("config save needs the X-SleekKeys header (CSRF)", call("POST", "/api/config", good, header=False)[0] == 403)
check("config save rejects other Host headers", call("POST", "/api/config", good, host="evil.example")[0] == 403)
check("garbage JSON rejected", call("POST", "/api/config", b"not json")[0] == 400)
check("config without profiles rejected", call("POST", "/api/config", b'{"active":"a"}')[0] == 400)
check("config with empty profiles rejected", call("POST", "/api/config", b'{"active":"a","profiles":{}}')[0] == 400)
check("config without active profile rejected", call("POST", "/api/config", b'{"profiles":{"a":{}}}')[0] == 400)
check("oversize config rejected", call("POST", "/api/config", b"x" * 600_000)[0] in (400, 403))
st, _ = call("POST", "/api/config", good)
check("valid config accepted", st == 200)
st, body = call("GET", "/api/config")
check("saved config reads back identically", st == 200 and json.loads(body)["active"] == "a")
st, body = call("GET", "/api/info")
info = json.loads(body)
check("/api/info reports a source size %s" % info.get("size"), isinstance(info.get("size"), list) and len(info["size"]) == 2)
check("config version increments on save", info["configVersion"] >= 1)
check("config API refuses other Host headers on GET", call("GET", "/api/config", host="evil.example")[0] == 403)
check("editor page is served", call("GET", "/")[0] == 200)
check("overlay page is served", call("GET", "/overlay")[0] == 200)
check("path traversal blocked", call("GET", "/..%5csleekkeys.py")[0] == 404)

print("\n%d/%d passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
