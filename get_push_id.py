"""
Get Gemini's push-id

push-id is a necessary parameter for image uploads, in the format feeds/xxxxx
It needs to be obtained from the Gemini page or API
"""

import httpx
import re
from config import SECURE_1PSID, SECURE_1PSIDTS, SECURE_1PSIDCC, COOKIES_STR


def get_push_id_from_page():
    """Get push-id from Gemini page"""
    print("Getting push-id...")
    
    session = httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    
    # Set cookies
    if COOKIES_STR:
        for item in COOKIES_STR.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                session.cookies.set(key.strip(), value.strip(), domain=".google.com")
    else:
        session.cookies.set("__Secure-1PSID", SECURE_1PSID, domain=".google.com")
        if SECURE_1PSIDTS:
            session.cookies.set("__Secure-1PSIDTS", SECURE_1PSIDTS, domain=".google.com")
        if SECURE_1PSIDCC:
            session.cookies.set("__Secure-1PSIDCC", SECURE_1PSIDCC, domain=".google.com")
    
    try:
        # Access Gemini homepage
        resp = session.get("https://gemini.google.com")
        
        if resp.status_code != 200:
            print(f"❌ Access failed: {resp.status_code}")
            return None
        
        html = resp.text
        
        # Try multiple patterns to match push-id
        patterns = [
            r'"push[_-]?id["\s:]+["\'](feeds/[a-z0-9]+)["\']',  # "push_id": "feeds/xxx"
            r'push[_-]?id["\s:=]+["\'](feeds/[a-z0-9]+)["\']',  # push_id="feeds/xxx"
            r'feedName["\s:]+["\'](feeds/[a-z0-9]+)["\']',      # "feedName": "feeds/xxx"
            r'clientId["\s:]+["\'](feeds/[a-z0-9]+)["\']',      # "clientId": "feeds/xxx"
            r'(feeds/[a-z0-9]{14,})',                            # 直接匹配 feeds/xxx 格式
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                push_id = matches[0]
                print(f"✅ Found push-id: {push_id}")
                return push_id
        
        # If not found, save page source for analysis
        with open("gemini_page_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("❌ push-id not found")
        print("   Page source saved to gemini_page_debug.html")
        print("   Please manually search for 'feeds/' or 'push' keywords")
        
        return None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def get_push_id_from_api():
    """Try to get push-id from API"""
    print("\nTrying to get push-id from API...")
    
    session = httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }
    )
    
    # Set cookies
    if COOKIES_STR:
        for item in COOKIES_STR.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                session.cookies.set(key.strip(), value.strip(), domain=".google.com")
    else:
        session.cookies.set("__Secure-1PSID", SECURE_1PSID, domain=".google.com")
    
    # Possible API endpoints
    endpoints = [
        "https://gemini.google.com/_/BardChatUi/data/batchexecute",
        "https://push.clients6.google.com/v1/feeds",
    ]
    
    for endpoint in endpoints:
        try:
            resp = session.get(endpoint)
            print(f"  {endpoint}: {resp.status_code}")
            if resp.status_code == 200:
                # Try to extract push-id from response
                text = resp.text
                match = re.search(r'feeds/[a-z0-9]{14,}', text)
                if match:
                    push_id = match.group(0)
                    print(f"  ✅ Found: {push_id}")
                    return push_id
        except Exception as e:
            print(f"  ❌ {endpoint}: {e}")
    
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("Get Gemini push-id")
    print("=" * 60)
    
    # Method 1: Get from page
    push_id = get_push_id_from_page()
    
    # Method 2: Get from API
    if not push_id:
        push_id = get_push_id_from_api()
    
    if push_id:
        print("\n" + "=" * 60)
        print(f"✅ Successfully obtained push-id: {push_id}")
        print("=" * 60)
        print("\nPlease add this value to config.py:")
        print(f'PUSH_ID = "{push_id}"')
    else:
        print("\n" + "=" * 60)
        print("❌ Failed to automatically obtain push-id")
        print("=" * 60)
        print("\nManual retrieval method:")
        print("1. Open https://gemini.google.com and log in")
        print("2. Press F12 to open Developer Tools -> Network tab")
        print("3. Upload an image")
        print("4. Find the upload request")
        print("5. In the request headers, find push-id or x-goog-upload-header-content-length")
        print("6. Copy the value in the format feeds/xxxxx")