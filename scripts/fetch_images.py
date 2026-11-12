"""Amazon Creators API (credential v3.3 / FE) で商品画像と商品ページURLを取得し products.json に書き込む。

- asin が無い商品は query で searchItems し、商品名と一致する先頭候補の ASIN を採用する
- asin がある商品は getItems で画像・URLを毎日取り直す（Amazonの規約で24時間以内に更新が必要）
- 利用資格が無い(403)・認証失敗のときは image/url を消してイラスト表示に戻す
環境変数: AMAZON_CREDENTIAL_ID, AMAZON_CREDENTIAL_SECRET
"""
import json, os, re, sys, time, unicodedata
import urllib.request, urllib.parse, urllib.error

PARTNER_TAG = "rungenic-22"
MARKETPLACE = "www.amazon.co.jp"
TOKEN_URL = "https://api.amazon.co.jp/auth/o2/token"
API = "https://creatorsapi.amazon/catalog/v1/"
DATA = os.path.join(os.path.dirname(__file__), "..", "products.json")


class NotEligible(Exception):
    pass


def post(url, body, headers, form=False):
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    h = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json", **headers}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw.decode(errors="replace")[:500]}


def get_token():
    body = {
        "grant_type": "client_credentials",
        "client_id": os.environ["AMAZON_CREDENTIAL_ID"],
        "client_secret": os.environ["AMAZON_CREDENTIAL_SECRET"],
        "scope": "creatorsapi::default",
    }
    for form in (False, True):
        st, d = post(TOKEN_URL, body, {}, form=form)
        if st == 200 and d.get("access_token"):
            return d["access_token"]
        print(f"token ({'form' if form else 'json'}) -> {st} {d}", file=sys.stderr)
    raise RuntimeError("アクセストークンを取得できませんでした（Credential ID/Secret を確認してください）")


def call(token, op, body):
    body = {"partnerTag": PARTNER_TAG, "marketplace": MARKETPLACE, **body}
    for attempt in range(3):
        st, d = post(API + op, body, {"Authorization": f"Bearer {token}", "x-marketplace": MARKETPLACE})
        if st == 200:
            return d
        text = json.dumps(d, ensure_ascii=False)
        if st == 403 and "NotEligible" in text:
            raise NotEligible(text)
        if st == 429:
            time.sleep(2 + attempt * 3)
            continue
        print(f"{op} -> {st} {text[:400]}", file=sys.stderr)
        return None
    return None


def find(d, *keys):
    """レスポンスのキー名の揺れ（searchResult/SearchResult など）を吸収して取り出す"""
    for k in keys:
        if isinstance(d, dict):
            m = {x.lower(): x for x in d}
            d = d.get(m.get(k.lower(), k))
        else:
            return None
    return d


def items_of(resp, *path):
    v = find(resp, *path)
    return v if isinstance(v, list) else []


def image_of(item):
    for size in ("large", "medium", "small"):
        u = find(item, "images", "primary", size, "url")
        if u:
            return u
    return None


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[\s\-・/（）()]", "", s)


def matches(name, title):
    """商品名の主要な語（ブランド・モデル名）がタイトルにすべて含まれるか"""
    t = norm(title)
    words = [w for w in re.split(r"[\s　]+", unicodedata.normalize("NFKC", name)) if w and not re.fullmatch(r"[（(].*[）)]", w)]
    words = [norm(w) for w in words if len(norm(w)) >= 2]
    return bool(words) and all(w in t for w in words)


def main():
    data = json.load(open(DATA, encoding="utf-8"))
    products = data["products"]
    try:
        token = get_token()
        # 1) ASIN 未設定の商品を検索で特定
        for p in products:
            if p.get("asin") or p.get("asin_checked"):
                continue
            resp = call(token, "searchItems", {
                "keywords": p.get("query") or p["name"], "itemCount": 5,
                "resources": ["itemInfo.title"]})
            p["asin_checked"] = True
            if not resp:
                continue
            for it in items_of(resp, "searchResult", "items"):
                title = find(it, "itemInfo", "title", "displayValue") or ""
                if matches(p["name"], title):
                    p["asin"] = find(it, "asin")
                    print(f"ASIN {p['id']} {p['name']} -> {p['asin']} ({title[:40]})")
                    break
            else:
                print(f"一致なし {p['id']} {p['name']}（検索リンクのまま）")
            time.sleep(1.1)

        # 2) ASIN のある商品の画像・URLを取得（10件ずつ）
        with_asin = [p for p in products if p.get("asin")]
        got = {}
        for i in range(0, len(with_asin), 10):
            ids = [p["asin"] for p in with_asin[i:i + 10]]
            resp = call(token, "getItems", {
                "itemIds": ids, "itemIdType": "ASIN",
                "resources": ["images.primary.large", "images.primary.medium", "itemInfo.title"]})
            for it in items_of(resp or {}, "itemsResult", "items"):
                got[find(it, "asin")] = (image_of(it), find(it, "detailPageURL"))
            time.sleep(1.1)
        for p in products:
            img, url = got.get(p.get("asin"), (None, None))
            p.pop("image", None); p.pop("url", None)
            if img:
                p["image"] = img
            if url:
                p["url"] = url
        print(f"画像あり {sum(1 for p in products if p.get('image'))}/{len(products)}件")
    except NotEligible as e:
        print("Creators API の利用資格がありません（直近30日の発送済み10件未満）。イラスト表示に戻します。", e, file=sys.stderr)
        for p in products:
            p.pop("image", None); p.pop("url", None)
    data["images_updated"] = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 9 * 3600))
    save(data)


def save(data):
    lines = ["{"]
    lines.append(f'  "updated": {json.dumps(data["updated"])},')
    if data.get("images_updated"):
        lines.append(f'  "images_updated": {json.dumps(data["images_updated"])},')
    lines.append(f'  "categories": {json.dumps(data["categories"], ensure_ascii=False)},')
    lines.append('  "products": [')
    ps = [ "    " + json.dumps(p, ensure_ascii=False) for p in data["products"]]
    lines.append(",\n".join(ps))
    lines.append("  ]")
    lines.append("}")
    with open(DATA, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
