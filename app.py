import os
import random
import re
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

targetHost = "https://app.khaddavi.net"
userAgent = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
)

app = Flask(__name__)

@app.get("/")
def home():
    # Vercel rewrite /bypass -> /api/index bikin path jadi "/"
    # Jadi kalo ada ?url= / ?slug=, anggap ini request bypass
    if request.args.get("url") or request.args.get("slug"):
        return resolveEndpoint()
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "index.html"), "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


def getXsrf(session, domain):
    for cookie in session.cookies:
        if cookie.name == "XSRF-TOKEN" and domain in cookie.domain:
            return unquote(cookie.value)
    return ""

def extractDestination(html):
    # 1. Cari yang paling utama: window.location.href = "https://safefileku..."
    m = re.search(r'window\.location\.href\s*=\s*["\']([^"\']+)["\']', html)
    if m:
        return m.group(1).replace("\\/", "/")
    # 2. Fallback: meta refresh
    m = re.search(r'http-equiv=["\']refresh["\'][^>]+url=([^"\'>\s]+)', html, re.I)
    if m:
        return m.group(1)
    # 3. Fallback: kalo HTML nya udah ada link safefileku langsung
    if "safefileku.com/download/" in html:
        m = re.search(r'https://safefileku\.com/download/[A-Za-z0-9]+', html)
        if m:
            return m.group(0)
    return None

def resolve(slug):
    session = requests.Session()
    session.headers.update({
        "User-Agent": userAgent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    # === TAHAP 1: Ambil sfl.gl ===
    page = session.get(f"https://sfl.gl/{slug}", timeout=30)
    soup = BeautifulSoup(page.text, "html.parser")
    form = soup.find("form")

    if not form:
        # FIX: Kalo form gak ada, cari ray_id manual (kayak cara curl lu)
        m = re.search(r'ray_id["\']?\s*value=["\']([^"\']+)', page.text)
        if m:
            landed = session.get(
                f"{targetHost}/redirect.php?alias={slug}&ray_id={m.group(1)}",
                timeout=30, allow_redirects=True
            )
        else:
            # FIX: Kalo gak ada form & gak ada ray_id, coba langsung redirect.php
            landed = session.get(
                f"{targetHost}/redirect.php?alias={slug}",
                timeout=30, allow_redirects=True
            )
    else:
        action = urljoin(page.url, form.get("action") or page.url)
        formData = {
            f.get("name"): f.get("value", "")
            for f in form.find_all("input")
            if f.get("name")
        }
        landed = session.get(action, params=formData, timeout=30, allow_redirects=True)

    referer = landed.url
    if "khaddavi" not in referer:
        raise ValueError(f"did not land on {targetHost}, got {referer}")

    # === TAHAP 2: Ambil XSRF ===
    xsrf = getXsrf(session, "khaddavi")
    if not xsrf:
        raise ValueError("no XSRF-TOKEN for app.khaddavi.net")

    apiHeaders = {
        "Content-Type": "application/json",
        "X-XSRF-TOKEN": xsrf,
        "Origin": targetHost,
        "Referer": referer,
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
    }

    # === TAHAP 3: Verify ===
    session.post(
        f"{targetHost}/api/verify",
        headers=apiHeaders,
        json={"_a": 0, "captcha": "", "passcode": ""},
        timeout=30,
    )

    # === TAHAP 4: Loop /api/go sampe ketemu safefileku ===
    # FIX: Di-loop 3x karena kadang masih dikasih artikel ke-2 dulu
    for _ in range(3):
        key = random.randint(0, 999)
        size = f"{3840 + key * 2}.{2160 + key * 2}"
        go = session.post(
            f"{targetHost}/api/go",
            headers=apiHeaders,
            json={"key": key, "size": size},
            timeout=30,
        ).json()

        goUrl = go.get("url")
        if not goUrl:
            raise ValueError(f"no url in /api/go response: {go}")

        ready = session.get(goUrl, timeout=30, allow_redirects=True)
        final = extractDestination(ready.text)

        # STOP DI SINI! Jangan lanjut ke download file nya
        # Kalo udah safefileku, langsung return
        if final and "safefileku.com/download/" in final:
            return final

        # Kalo belum, update referer buat loop berikutnya
        apiHeaders["Referer"] = ready.url

    raise ValueError("destination not found after 3 tries")

@app.get("/bypass")
@app.get("/api/index")
def resolveEndpoint():
    slug = request.args.get("slug")
    if not slug:
        url = request.args.get("url", "")
        slug = url.rstrip("/").split("/")[-1]
    if not slug:
        return jsonify(error="missing slug"), 400

    try:
        return jsonify(slug=slug, url=resolve(slug))
    except Exception as err:
        return jsonify(error=str(err)), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
