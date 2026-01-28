"""
Gemini OpenAI Compatible API Service

Start: python server.py
Admin: http://localhost:8000/admin
API:   http://localhost:8000/v1
"""

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import uvicorn
import time
import uuid
import json
import os
import re
import httpx
import hashlib
import secrets

# ============ Configuration ============
API_KEY = "sk-gemini"
HOST = "0.0.0.0"
PORT = 8000
CONFIG_FILE = "config_data.json"
# Admin login credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
# ========================================

app = FastAPI(title="Gemini OpenAI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file routes (for sample images)
from fastapi.responses import FileResponse

# Generated media file cache directory
MEDIA_CACHE_DIR = os.path.join(os.path.dirname(__file__), "media_cache")
os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

@app.get("/static/{filename}")
async def serve_static(filename: str):
    """Serve static files (sample images, etc.)"""
    file_path = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/media/{media_id}")
async def serve_media(media_id: str):
    """Serve cached media files"""
    # Security check: only allow alphanumeric and underscores
    if not media_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid media ID")
    
    # Find matching file
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4"]:
        file_path = os.path.join(MEDIA_CACHE_DIR, media_id + ext)
        if os.path.exists(file_path):
            return FileResponse(file_path)
    
    raise HTTPException(status_code=404, detail="Media file not found")

def cleanup_old_media(max_age_hours: int = 1):
    """Clean up expired media cache files"""
    import time
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        for filename in os.listdir(MEDIA_CACHE_DIR):
            file_path = os.path.join(MEDIA_CACHE_DIR, filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
    except Exception:
        pass

# 存储有效的 session token
_admin_sessions = set()

def generate_session_token():
    """Generate random session token"""
    return secrets.token_hex(32)

def verify_admin_session(request: Request):
    """Verify admin session"""
    token = request.cookies.get("admin_session")
    if not token or token not in _admin_sessions:
        return False
    return True

# Default available models list (Gemini 3 official three models: Flash/Thinking/Pro)
DEFAULT_MODELS = ["gemini-3.0-flash", "gemini-3.0-flash-thinking", "gemini-3.0-pro"]

# Default model IDs (used for request header model selection)
DEFAULT_MODEL_IDS = {
    "flash": "56fdd199312815e2",
    "pro": "e6fa609c3fa255c0", 
    "thinking": "e051ce1aa80aa576",
}

# Configuration storage
_config = {
    "SNLM0E": "",
    "SECURE_1PSID": "",
    "SECURE_1PSIDTS": "",
    "SAPISID": "",
    "SID": "",
    "HSID": "",
    "SSID": "",
    "APISID": "",
    "PUSH_ID": "",
    "FULL_COOKIE": "",  # Store complete cookie string
    "MODELS": DEFAULT_MODELS.copy(),  # Available models list
    "MODEL_IDS": DEFAULT_MODEL_IDS.copy(),  # Model ID mapping
}

# Cookie field mapping (browser cookie name -> config field name)
COOKIE_FIELD_MAP = {
    "__Secure-1PSID": "SECURE_1PSID",
    "__Secure-1PSIDTS": "SECURE_1PSIDTS",
    "SAPISID": "SAPISID",
    "__Secure-1PAPISID": "SAPISID",  # 也映射到 SAPISID
    "SID": "SID",
    "HSID": "HSID",
    "SSID": "SSID",
    "APISID": "APISID",
}


def parse_cookie_string(cookie_str: str) -> dict:
    """Parse complete cookie string and extract required fields"""
    result = {}
    if not cookie_str:
        return result
    
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            eq_index = item.index("=")
            key = item[:eq_index].strip()
            value = item[eq_index + 1:].strip()
            if key in COOKIE_FIELD_MAP:
                result[COOKIE_FIELD_MAP[key]] = value
    
    return result


def fetch_tokens_from_page(cookies_str: str) -> dict:
    """Automatically fetch SNLM0E, PUSH_ID and available models list from Gemini page"""
    result = {"snlm0e": "", "push_id": "", "models": []}
    try:
        session = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        
        # 设置 cookies
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                session.cookies.set(key.strip(), value.strip(), domain=".google.com")
        
        resp = session.get("https://gemini.google.com")
        if resp.status_code != 200:
            return result
        
        html = resp.text
        
        # 获取 SNLM0E (AT Token)
        snlm0e_patterns = [
            r'"SNlM0e":"([^"]+)"',
            r'SNlM0e["\s:]+["\']([^"\']+)["\']',
            r'"at":"([^"]+)"',
        ]
        for pattern in snlm0e_patterns:
            match = re.search(pattern, html)
            if match:
                result["snlm0e"] = match.group(1)
                break
        
        # 获取 PUSH_ID
        push_id_patterns = [
            r'"push[_-]?id["\s:]+["\'](feeds/[a-z0-9]+)["\']',
            r'push[_-]?id["\s:=]+["\'](feeds/[a-z0-9]+)["\']',
            r'feedName["\s:]+["\'](feeds/[a-z0-9]+)["\']',
            r'clientId["\s:]+["\'](feeds/[a-z0-9]+)["\']',
            r'(feeds/[a-z0-9]{14,})',
        ]
        for pattern in push_id_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                result["push_id"] = matches[0]
                break
        
        # Get available models list (extract gemini model IDs from page)
        model_patterns = [
            r'"(gemini-[a-z0-9\.\-]+)"',  # Match "gemini-xxx" format
            r"'(gemini-[a-z0-9\.\-]+)'",  # Match 'gemini-xxx' format
        ]
        models_found = set()
        for pattern in model_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for m in matches:
                # Filter valid model names
                if any(x in m.lower() for x in ['flash', 'pro', 'ultra', 'nano']):
                    models_found.add(m)
        
        if models_found:
            result["models"] = sorted(list(models_found))
        
        # Get model IDs (for x-goog-ext-525001261-jspb request header)
        # These IDs are used to select different model versions
        model_id_pattern = r'\["([a-f0-9]{16})","gemini[^"]*(?:flash|pro|thinking)[^"]*"\]'
        model_ids = re.findall(model_id_pattern, html, re.IGNORECASE)
        if model_ids:
            result["model_ids"] = list(set(model_ids))
        
        # Fallback: directly search for 16-digit hex IDs (near model configuration)
        if not result.get("model_ids"):
            # Search for patterns like "56fdd199312815e2"
            hex_id_pattern = r'"([a-f0-9]{16})"'
            # Search within context containing gemini or model
            context_pattern = r'.{0,100}(?:gemini|model|flash|pro|thinking).{0,100}'
            contexts = re.findall(context_pattern, html, re.IGNORECASE)
            hex_ids = set()
            for ctx in contexts:
                ids = re.findall(hex_id_pattern, ctx)
                hex_ids.update(ids)
            if hex_ids:
                result["model_ids"] = list(hex_ids)
        
        return result
    except Exception:
        return result

_client = None


# ============ Tools Support ============
def build_tools_prompt(tools: List[Dict]) -> str:
    """Convert tools definition to prompt"""
    if not tools:
        return ""
    
    tools_schema = json.dumps([{
        "name": t["function"]["name"],
        "description": t["function"].get("description", ""),
        "parameters": t["function"].get("parameters", {})
    } for t in tools if t.get("type") == "function"], ensure_ascii=False, indent=2)
    
    prompt = f"""[System] You have access to these functions. Use them when needed to accomplish the user's request:

Available functions:
{tools_schema}

When you need to call a function, output ONLY this format:
```tool_call
{{"name": "function_name", "arguments": {{"param": "value"}}}}
```

When you receive tool results, analyze them and either:
- Call another function if more information is needed
- Provide your final answer based on the results

User request: """
    return prompt


def parse_tool_calls(content: str) -> tuple:
    """
    Parse tool calls in response
    Returns: (list of tool_calls, remaining text content)
    """
    tool_calls = []
    
    # Multiple matching patterns
    patterns = [
        r'```tool_call\s*\n?(.*?)\n?```',  # ```tool_call ... ```
        r'```json\s*\n?(.*?)\n?```',        # ```json ... ``` (sometimes models use this)
        r'```\s*\n?(\{[^`]*"name"[^`]*\})\n?```',  # ``` {...} ```
    ]
    
    matches = []
    for pattern in patterns:
        found = re.findall(pattern, content, re.DOTALL)
        matches.extend(found)
    
    # Also try to match JSON objects directly (without code block wrapper)
    if not matches:
        json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
    
    for i, match in enumerate(matches):
        try:
            match = match.strip()
            # Try to parse JSON
            call_data = json.loads(match)
            if call_data.get("name"):
                tool_calls.append({
                    "index": i,
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": call_data.get("name", ""),
                        "arguments": json.dumps(call_data.get("arguments", {}), ensure_ascii=False)
                    }
                })
        except json.JSONDecodeError:
            continue
    
    # Remove tool call sections
    remaining = content
    for pattern in patterns:
        remaining = re.sub(pattern, '', remaining, flags=re.DOTALL)
    remaining = remaining.strip()
    
    return tool_calls, remaining


def load_config():
    """
    Load configuration, priority:
    1. config_data.json (frontend saved configuration)
    2. config.py (local development configuration, as fallback only)
    """
    global _config
    loaded_from_json = False
    
    # Load from JSON file first
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("SNLM0E") and saved.get("SECURE_1PSID"):
                    _config.update(saved)
                    loaded_from_json = True
        except:
            pass
    
    # If JSON has no valid config, try loading from config.py
    if not loaded_from_json:
        try:
            import config
            for key in _config:
                if hasattr(config, key) and getattr(config, key):
                    _config[key] = getattr(config, key)
        except:
            pass


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(_config, f, indent=2, ensure_ascii=False)


def get_client():
    global _client
    
    if not _config.get("SNLM0E") or not _config.get("SECURE_1PSID"):
        raise HTTPException(status_code=500, detail="Please configure Token and Cookie in admin panel first")
    
    # If client already exists, reuse it to maintain session context
    if _client is not None:
        return _client
    
    cookies = f"__Secure-1PSID={_config['SECURE_1PSID']}"
    if _config.get("SECURE_1PSIDTS"):
        cookies += f"; __Secure-1PSIDTS={_config['SECURE_1PSIDTS']}"
    if _config.get("SAPISID"):
        cookies += f"; SAPISID={_config['SAPISID']}; __Secure-1PAPISID={_config['SAPISID']}"
    if _config.get("SID"):
        cookies += f"; SID={_config['SID']}"
    if _config.get("HSID"):
        cookies += f"; HSID={_config['HSID']}"
    if _config.get("SSID"):
        cookies += f"; SSID={_config['SSID']}"
    if _config.get("APISID"):
        cookies += f"; APISID={_config['APISID']}"
    
    # Build base URL for media files
    media_base_url = f"http://localhost:{PORT}"
    
    from client import GeminiClient
    _client = GeminiClient(
        secure_1psid=_config["SECURE_1PSID"],
        snlm0e=_config["SNLM0E"],
        cookies_str=cookies,
        push_id=_config.get("PUSH_ID") or None,
        model_ids=_config.get("MODEL_IDS") or DEFAULT_MODEL_IDS,
        debug=True,
        media_base_url=media_base_url,
    )
    return _client


def get_login_html():
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Gemini API</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; 
            display: flex; align-items: center; justify-content: center; padding: 20px; }
        .login-card { background: white; border-radius: 16px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; text-align: center; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; text-align: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 8px; }
        input { width: 100%; padding: 14px 16px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 15px; transition: border-color 0.2s; }
        input:focus { outline: none; border-color: #667eea; }
        .btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 30px;
            border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 10px; transition: transform 0.2s, box-shadow 0.2s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102,126,234,0.4); }
        .btn:disabled { opacity: 0.7; cursor: not-allowed; transform: none; }
        .error { background: #f8d7da; color: #721c24; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; display: none; }
        .logo { text-align: center; margin-bottom: 20px; font-size: 48px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">🤖</div>
        <h1>Gemini API</h1>
        <p class="subtitle">Please login to access admin panel</p>
        
        <div id="error" class="error"></div>
        
        <form id="loginForm">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" id="username" placeholder="Enter username" required autofocus>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" id="password" placeholder="Enter password" required>
            </div>
            <button type="submit" class="btn" id="submitBtn">Login</button>
        </form>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorEl = document.getElementById('error');
            const submitBtn = document.getElementById('submitBtn');
            
            errorEl.style.display = 'none';
            submitBtn.disabled = true;
            submitBtn.textContent = '登录中...';
            
            try {
                const resp = await fetch('/admin/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: document.getElementById('username').value,
                        password: document.getElementById('password').value
                    })
                });
                const result = await resp.json();
                
                if (result.success) {
                    window.location.href = '/admin';
                } else {
                    errorEl.textContent = result.message || '登录失败';
                    errorEl.style.display = 'block';
                }
            } catch (err) {
                errorEl.textContent = '网络错误: ' + err.message;
                errorEl.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '登 录';
            }
        });
    </script>
</body>
</html>'''


def get_admin_html():
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini API Configuration</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { background: white; border-radius: 16px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .section { margin-bottom: 25px; }
        .section-title { font-size: 16px; font-weight: 600; color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #eee; }
        .required { color: #e74c3c; }
        .optional { color: #95a5a6; font-size: 12px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-size: 13px; font-weight: 500; color: #555; margin-bottom: 5px; }
        input, textarea { width: 100%; padding: 12px 15px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; font-family: monospace; transition: border-color 0.2s; }
        input:focus, textarea:focus { outline: none; border-color: #667eea; }
        textarea { resize: vertical; min-height: 80px; }
        .btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 30px;
            border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 20px; transition: transform 0.2s, box-shadow 0.2s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102,126,234,0.4); }
        .status { margin-top: 20px; padding: 15px; border-radius: 8px; font-size: 14px; display: none; }
        .status.success { background: #d4edda; color: #155724; display: block; }
        .status.error { background: #f8d7da; color: #721c24; display: block; }
        .info-box { background: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-size: 13px; color: #666; }
        .info-box code { background: #e9ecef; padding: 2px 6px; border-radius: 4px; }
        .api-info { background: #e8f4fd; border-left: 4px solid #667eea; padding: 15px; margin-top: 20px; border-radius: 0 8px 8px 0; }
        .api-info h3 { font-size: 14px; margin-bottom: 10px; color: #333; }
        .api-info pre { background: #fff; padding: 10px; border-radius: 4px; font-size: 12px; margin-top: 5px; overflow-x: auto; }
        .parsed-info { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 15px; margin-top: 15px; font-size: 12px; display: none; }
        .parsed-info h4 { color: #0369a1; margin-bottom: 10px; }
        .parsed-info .item { margin: 5px 0; color: #555; }
        .parsed-info .item span { color: #059669; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🤖 Gemini API Configuration</h1>
            <p class="subtitle">Configure Google Gemini authentication, API ready after saving <a href="/admin/logout" style="float:right;color:#667eea;text-decoration:none;">Logout</a></p>
            
            <div class="info-box">
                <strong>How to get:</strong><br>
                1. Open <a href="https://gemini.google.com" target="_blank">gemini.google.com</a> and login<br>
                2. F12 → Network → Send message to chat → Click any request → Copy complete cookie from request headers
            </div>
            
            <form id="configForm">
                <div class="section">
                    <div class="section-title">🔑 Cookie Configuration</div>
                    <div class="form-group">
                        <label>Complete Cookie <span class="required">*</span></label>
                        <textarea name="FULL_COOKIE" id="FULL_COOKIE" rows="6" placeholder="Paste complete Cookie string copied from browser, system will auto-parse required fields and Token..." required></textarea>
                        <div id="parsedInfo" class="parsed-info">
                            <h4>✅ Parsed fields:</h4>
                            <div id="parsedFields"></div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <div class="section-title">🎯 Model ID Configuration <span class="optional">(Optional, update if model switching fails)</span></div>
                    <div class="info-box">
                        <strong>How to get:</strong> F12 → Network → Switch model in Gemini and send message → Find request header <code>x-goog-ext-525001261-jspb</code> → Copy entire array value and paste below
                    </div>
                    <div class="form-group">
                        <label>Quick Parse <span class="optional">(Paste request header array to auto-extract ID)</span></label>
                        <input type="text" id="MODEL_ID_PARSER" placeholder='Paste like: [1,null,null,null,"56fdd199312815e2",null,null,0,[4],null,null,2]'>
                        <div id="parsedModelId" class="parsed-info" style="margin-top:10px;">
                            <h4>✅ Extracted Model ID:</h4>
                            <div id="parsedModelIdValue"></div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Flash Version ID</label>
                        <input type="text" name="MODEL_ID_FLASH" id="MODEL_ID_FLASH" placeholder="56fdd199312815e2">
                    </div>
                    <div class="form-group">
                        <label>Pro Version ID</label>
                        <input type="text" name="MODEL_ID_PRO" id="MODEL_ID_PRO" placeholder="e6fa609c3fa255c0">
                    </div>
                    <div class="form-group">
                        <label>Thinking Version ID</label>
                        <input type="text" name="MODEL_ID_THINKING" id="MODEL_ID_THINKING" placeholder="e051ce1aa80aa576">
                    </div>
                </div>
                
                <button type="submit" class="btn">💾 Save Configuration</button>
            </form>
            
            <div id="status" class="status"></div>
            
            <div class="api-info">
                <h3>📡 API Call Information</h3>
                <p>Base URL: <strong id="baseUrl"></strong></p>
                <p>API Key: <strong id="apiKey"></strong></p>
                <p>Available models: <code>gemini-3.0-flash</code> | <code>gemini-3.0-pro</code> | <code>gemini-3.0-flash-thinking</code></p>
                
                <h4 style="margin-top:15px;">💬 Text Chat</h4>
<pre>from openai import OpenAI
client = OpenAI(base_url="<span id="codeUrl"></span>", api_key="<span id="codeKey"></span>")

response = client.chat.completions.create(
    model="gemini-3.0-flash",  # or gemini-3.0-pro / gemini-3.0-flash-thinking
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)</pre>

                <h4 style="margin-top:15px;">🖼️ Image Recognition</h4>
<pre>import base64
from openai import OpenAI
client = OpenAI(base_url="<span id="codeUrl2"></span>", api_key="<span id="codeKey2"></span>")

# Read local image
with open("image.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Please describe this image"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]
    }]
)
print(response.choices[0].message.content)</pre>

                <h4 style="margin-top:15px;">🌊 Streaming Response</h4>
<pre>stream = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "Write a poem"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)</pre>

                <h4 style="margin-top:15px;">📷 Sample Image</h4>
                <p style="font-size:12px;color:#666;">Below is image.png sample image, can be used to test image recognition (click to enlarge):</p>
                <img id="sampleImage" src="/static/image.png" alt="Sample Image" style="max-width:300px;border-radius:8px;margin-top:10px;border:1px solid #ddd;cursor:pointer;" onclick="showImageModal()" onerror="this.style.display='none';this.nextElementSibling.style.display='block';">
                <p style="display:none;font-size:12px;color:#999;">(Sample image unavailable, please ensure image.png file exists)</p>
            </div>
        </div>
    </div>
    
    <!-- 图片放大模态框 -->
    <div id="imageModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;justify-content:center;align-items:center;cursor:pointer;" onclick="hideImageModal()">
        <img src="/static/image.png" alt="Sample Image" style="max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 0 30px rgba(0,0,0,0.5);">
        <span style="position:absolute;top:20px;right:30px;color:white;font-size:30px;cursor:pointer;">&times;</span>
    </div>
    
    <script>
        // Image zoom functionality
        function showImageModal() {
            document.getElementById('imageModal').style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
        function hideImageModal() {
            document.getElementById('imageModal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }
        // Close with ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hideImageModal();
        });
        
        const API_KEY = "''' + API_KEY + '''";
        const PORT = ''' + str(PORT) + ''';
        
        document.getElementById('baseUrl').textContent = 'http://localhost:' + PORT + '/v1';
        document.getElementById('apiKey').textContent = API_KEY;
        document.getElementById('codeUrl').textContent = 'http://localhost:' + PORT + '/v1';
        document.getElementById('codeKey').textContent = API_KEY;
        document.getElementById('codeUrl2').textContent = 'http://localhost:' + PORT + '/v1';
        document.getElementById('codeKey2').textContent = API_KEY;
        
        // 解析模型 ID (从 x-goog-ext-525001261-jspb 数组中提取)
        function parseModelId(input) {
            try {
                // 尝试解析 JSON 数组
                const arr = JSON.parse(input);
                if (Array.isArray(arr) && arr.length > 4 && typeof arr[4] === 'string') {
                    return arr[4];
                }
            } catch (e) {
                // Try to extract 16-digit hex string with regex
                const match = input.match(/["\']([a-f0-9]{16})["\']/i);
                if (match) {
                    return match[1];
                }
            }
            return null;
        }
        
        // Listen to model ID parser input
        document.getElementById('MODEL_ID_PARSER').addEventListener('input', (e) => {
            const modelId = parseModelId(e.target.value);
            const container = document.getElementById('parsedModelIdValue');
            const infoBox = document.getElementById('parsedModelId');
            
            if (modelId) {
                container.innerHTML = '<div class="item">提取到的 ID: <span style="color:#059669;font-family:monospace;">' + modelId + '</span></div>' +
                    '<div style="margin-top:10px;">' +
                    '<button type="button" onclick="fillModelId(\\'flash\\', \\'' + modelId + '\\')" style="margin-right:5px;padding:5px 10px;cursor:pointer;">填入极速版</button>' +
                    '<button type="button" onclick="fillModelId(\\'pro\\', \\'' + modelId + '\\')" style="margin-right:5px;padding:5px 10px;cursor:pointer;">填入Pro版</button>' +
                    '<button type="button" onclick="fillModelId(\\'thinking\\', \\'' + modelId + '\\')" style="padding:5px 10px;cursor:pointer;">填入思考版</button>' +
                    '</div>';
                infoBox.style.display = 'block';
            } else {
                infoBox.style.display = 'none';
            }
        });
        
        // Fill model ID
        function fillModelId(type, id) {
            const fieldMap = {
                'flash': 'MODEL_ID_FLASH',
                'pro': 'MODEL_ID_PRO',
                'thinking': 'MODEL_ID_THINKING'
            };
            document.getElementById(fieldMap[type]).value = id;
        }
        
        // Cookie field mapping
        const cookieFields = {
            '__Secure-1PSID': 'SECURE_1PSID',
            '__Secure-1PSIDTS': 'SECURE_1PSIDTS',
            'SAPISID': 'SAPISID',
            '__Secure-1PAPISID': 'SECURE_1PAPISID',
            'SID': 'SID',
            'HSID': 'HSID',
            'SSID': 'SSID',
            'APISID': 'APISID'
        };
        
        // Parse Cookie string
        function parseCookie(cookieStr) {
            const result = {};
            if (!cookieStr) return result;
            
            cookieStr.split(';').forEach(item => {
                const trimmed = item.trim();
                const eqIndex = trimmed.indexOf('=');
                if (eqIndex > 0) {
                    const key = trimmed.substring(0, eqIndex).trim();
                    const value = trimmed.substring(eqIndex + 1).trim();
                    if (cookieFields[key]) {
                        result[cookieFields[key]] = value;
                    }
                }
            });
            return result;
        }
        
        // Display parsed results
        function showParsedFields(parsed) {
            const container = document.getElementById('parsedFields');
            const infoBox = document.getElementById('parsedInfo');
            
            const fieldNames = {
                'SECURE_1PSID': '__Secure-1PSID',
                'SECURE_1PSIDTS': '__Secure-1PSIDTS',
                'SAPISID': 'SAPISID',
                'SID': 'SID',
                'HSID': 'HSID',
                'SSID': 'SSID',
                'APISID': 'APISID'
            };
            
            let html = '';
            let hasFields = false;
            for (const [key, name] of Object.entries(fieldNames)) {
                if (parsed[key]) {
                    hasFields = true;
                    const shortValue = parsed[key].length > 30 ? parsed[key].substring(0, 30) + '...' : parsed[key];
                    html += '<div class="item">' + name + ': <span>' + shortValue + '</span></div>';
                }
            }
            
            if (hasFields) {
                container.innerHTML = html;
                infoBox.style.display = 'block';
            } else {
                infoBox.style.display = 'none';
            }
        }
        
        // Listen to Cookie input
        document.getElementById('FULL_COOKIE').addEventListener('input', (e) => {
            const parsed = parseCookie(e.target.value);
            showParsedFields(parsed);
        });
        
        // Load configuration
        fetch('/admin/config', {credentials: 'same-origin'}).then(r => {
            if (!r.ok) throw new Error('未登录');
            return r.json();
        }).then(config => {
            if (config.FULL_COOKIE) {
                document.getElementById('FULL_COOKIE').value = config.FULL_COOKIE;
                showParsedFields(parseCookie(config.FULL_COOKIE));
            }
            // Load model IDs
            if (config.MODEL_IDS) {
                document.getElementById('MODEL_ID_FLASH').value = config.MODEL_IDS.flash || '';
                document.getElementById('MODEL_ID_PRO').value = config.MODEL_IDS.pro || '';
                document.getElementById('MODEL_ID_THINKING').value = config.MODEL_IDS.thinking || '';
            }
        }).catch(err => {
            console.log('Failed to load configuration:', err);
        });
        
        document.getElementById('configForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            // Build model IDs object
            data.MODEL_IDS = {
                flash: data.MODEL_ID_FLASH || '',
                pro: data.MODEL_ID_PRO || '',
                thinking: data.MODEL_ID_THINKING || ''
            };
            delete data.MODEL_ID_FLASH;
            delete data.MODEL_ID_PRO;
            delete data.MODEL_ID_THINKING;
            
            const statusEl = document.getElementById('status');
            statusEl.className = 'status';
            statusEl.style.display = 'none';
            statusEl.textContent = '';
            
            // Display saving status
            const submitBtn = e.target.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = '⏳ Saving...';
            submitBtn.disabled = true;
            
            try {
                const resp = await fetch('/admin/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'same-origin',
                    body: JSON.stringify(data)
                });
                
                if (resp.status === 401) {
                    window.location.href = '/admin/login';
                    return;
                }
                
                const result = await resp.json();
                
                if (result.success) {
                    statusEl.className = 'status success';
                    statusEl.innerHTML = '✅ ' + result.message + '<br><br>💡 <strong>Configuration applied, no need to restart service!</strong>';
                } else {
                    statusEl.className = 'status error';
                    statusEl.textContent = '❌ ' + result.message;
                }
                statusEl.style.display = 'block';
            } catch (err) {
                statusEl.className = 'status error';
                statusEl.textContent = '❌ Save failed: ' + err.message;
                statusEl.style.display = 'block';
            } finally {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>'''


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page():
    return get_login_html()


@app.post("/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = generate_session_token()
        _admin_sessions.add(token)
        response = JSONResponse({"success": True, "message": "Login successful"})
        response.set_cookie(key="admin_session", value=token, httponly=True, max_age=86400)
        return response
    else:
        return {"success": False, "message": "Invalid username or password"}


@app.get("/admin/logout")
async def admin_logout(request: Request):
    token = request.cookies.get("admin_session")
    if token and token in _admin_sessions:
        _admin_sessions.discard(token)
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_session")
    return response


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not verify_admin_session(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_admin_html()


@app.post("/admin/save")
async def admin_save(request: Request):
    if not verify_admin_session(request):
        raise HTTPException(status_code=401, detail="Not logged in")
    
    global _client
    data = await request.json()
    
    # Process complete Cookie string, remove leading/trailing spaces
    full_cookie = data.get("FULL_COOKIE", "").strip()
    if not full_cookie:
        return {"success": False, "message": "Cookie is required"}
    
    # Parse Cookie string
    parsed = parse_cookie_string(full_cookie)
    
    if not parsed.get("SECURE_1PSID"):
        return {"success": False, "message": "__Secure-1PSID field not found in Cookie, please ensure you copied the complete Cookie"}
    
    # Automatically fetch SNLM0E and PUSH_ID from page
    tokens = fetch_tokens_from_page(full_cookie)
    
    if not tokens.get("snlm0e"):
        return {"success": False, "message": "Unable to automatically fetch AT Token, please check if Cookie is valid or expired"}
    
    # Update configuration
    _config["FULL_COOKIE"] = full_cookie
    _config["SNLM0E"] = tokens["snlm0e"]
    _config["PUSH_ID"] = tokens.get("push_id", "")
    
    # Update fields from parsed results
    for field in ["SECURE_1PSID", "SECURE_1PSIDTS", "SAPISID", "SID", "HSID", "SSID", "APISID"]:
        _config[field] = parsed.get(field, "")
    
    # Use automatically fetched models list, use default if fetch fails
    if tokens.get("models"):
        _config["MODELS"] = tokens["models"]
    else:
        _config["MODELS"] = DEFAULT_MODELS.copy()
    
    # Process model IDs configuration
    model_ids = data.get("MODEL_IDS", {})
    if model_ids:
        # Only update non-empty values
        if model_ids.get("flash"):
            _config["MODEL_IDS"]["flash"] = model_ids["flash"]
        if model_ids.get("pro"):
            _config["MODEL_IDS"]["pro"] = model_ids["pro"]
        if model_ids.get("thinking"):
            _config["MODEL_IDS"]["thinking"] = model_ids["thinking"]
    
    save_config()
    _client = None
    
    # Build result information
    parsed_fields = [k for k in ["SECURE_1PSID", "SECURE_1PSIDTS", "SAPISID", "SID", "HSID", "SSID", "APISID"] if parsed.get(k)]
    push_id_msg = f", PUSH_ID ✓" if tokens.get("push_id") else ", PUSH_ID ✗ (Image feature unavailable)"
    models_msg = f", {len(_config['MODELS'])} models" if _config.get("MODELS") else ""
    
    try:
        get_client()
        return {
            "success": True, 
            "message": f"Configuration saved and verified successfully! AT Token ✓{push_id_msg}{models_msg}",
            "need_restart": False
        }
    except Exception as e:
        return {
            "success": True, 
            "message": f"Configuration saved, but connection test failed: {str(e)[:50]}",
            "need_restart": False
        }


@app.get("/admin/config")
async def admin_get_config(request: Request):
    if not verify_admin_session(request):
        raise HTTPException(status_code=401, detail="Not logged in")
    return _config


# ============ API Routes ============

class ToolCallFunction(BaseModel):
    name: str
    arguments: str

class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction

class ChatMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[Dict[str, Any]]]] = None  # Optional for assistant messages with tool_calls
    name: Optional[str] = None
    tool_call_id: Optional[str] = None  # Required for tool results from opencode
    tool_calls: Optional[List[ToolCall]] = None  # For assistant messages that invoke tools
    
    class Config:
        extra = "ignore"


class FunctionDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class ToolDefinition(BaseModel):
    type: str = "function"
    function: FunctionDefinition

class ChatCompletionRequest(BaseModel):
    model: str = "gemini"
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    # Tools support
    tools: Optional[List[ToolDefinition]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    # Additional fields that OpenAI SDK may send
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    n: Optional[int] = None
    user: Optional[str] = None
    
    class Config:
        extra = "ignore"  # Ignore undefined extra fields


class ChatCompletionChoice(BaseModel):
    index: int
    message: Dict[str, Any]
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


def verify_api_key(authorization: str = Header(None)):
    if not API_KEY:
        return True
    if not authorization or not authorization.startswith("Bearer ") or authorization[7:] != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@app.get("/")
async def root():
    return RedirectResponse(url="/admin")


@app.get("/v1/models")
async def list_models(authorization: str = Header(None)):
    verify_api_key(authorization)
    models = _config.get("MODELS", DEFAULT_MODELS)
    created = int(time.time())
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": created, "owned_by": "google"} for m in models]
    }


def log_api_call(request_data: dict, response_data: dict, error: str = None):
    """Log API call to file"""
    import datetime
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "request": request_data,
        "response": response_data,
        "error": error
    }
    try:
        with open("log_api.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n---\n")
    except Exception as e:
        print(f"[LOG ERROR] 写入日志失败: {e}")


# Simplified session: trust Gemini's conversation_id
_last_request_time = 0
SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes of inactivity to reset


def extract_last_user_message(messages: list) -> list:
    """
    Extract relevant messages to send to Gemini.
    
    IMPORTANT for agents (opencode, etc.):
    - First check the LAST message to determine intent
    - If last message is 'tool'/'function', it's a tool call continuation
    - If last message is 'user', it's a NEW question (ignore old tools in history)
    """
    def to_dict(m):
        role = m.role if hasattr(m, 'role') else m.get('role', '')
        content = m.content if hasattr(m, 'content') else m.get('content', '')
        return {"role": role, "content": content}
    
    def get_role(m):
        return m.role if hasattr(m, 'role') else m.get('role', '')
    
    # DEBUG: Show all received messages
    # print(f"[DEBUG] Received {len(messages)} messages:")
    for i, m in enumerate(messages):
        role = get_role(m)
        content = m.content if hasattr(m, 'content') else m.get('content', '')
        content_preview = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
        tool_call_id = getattr(m, 'tool_call_id', None) or (m.get('tool_call_id') if isinstance(m, dict) else None)
        name = getattr(m, 'name', None) or (m.get('name') if isinstance(m, dict) else None)
        # print(f"  [{i}] role={role}, tool_call_id={tool_call_id}, name={name}, content={content_preview}")
    
    if not messages:
        return []
    
    # KEY: Check the LAST message type to determine intent
    last_message = messages[-1]
    last_role = get_role(last_message)
    
    print(f"[DEBUG] Last message has role={last_role}")
    
    # If last message is from user, it's a NEW question
    # Ignore any previous tool/function messages in history
    if last_role == 'user':
        print(f"[SESSION] New user question detected (ignoring tools history)")
        return [to_dict(last_message)]
    
    # If last message is tool/function, collect ONLY the tool results
    # that come at the end (after the last assistant)
    if last_role in ('tool', 'function'):
        # Find the index of the last assistant message
        last_assistant_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if get_role(messages[i]) == 'assistant':
                last_assistant_idx = i
                break
        
        # Collect only tool results that come AFTER the last assistant
        tool_results = []
        start_idx = last_assistant_idx + 1 if last_assistant_idx >= 0 else 0
        
        for m in messages[start_idx:]:
            role = get_role(m)
            if role in ('tool', 'function'):
                content = m.content if hasattr(m, 'content') else m.get('content', '')
                tool_call_id = getattr(m, 'tool_call_id', '') if hasattr(m, 'tool_call_id') else m.get('tool_call_id', '') if isinstance(m, dict) else ''
                name = getattr(m, 'name', '') if hasattr(m, 'name') else m.get('name', '') if isinstance(m, dict) else ''
                
                tool_name = name or tool_call_id or 'unknown_tool'
                tool_result = f"[Tool Result for {tool_name}]:\n{content}"
                tool_results.append(tool_result)
                print(f"[DEBUG] Found recent tool result: name={name}, id={tool_call_id}, content_len={len(str(content))}")
        
        if tool_results:
            print(f"[SESSION] Sending {len(tool_results)} recent tool result(s) to Gemini")
            combined_result = "\n\n".join(tool_results)
            instruction = (
                "The tool has been executed successfully. Here are the results:\n\n"
                f"{combined_result}\n\n"
                "Based on these results, please continue with the next step or provide your analysis. "
                "Do NOT call the same tool again with the same parameters - the results are already provided above."
            )
            return [{"role": "user", "content": instruction}]
    
    # Fallback: search for the last user message
    for m in reversed(messages):
        if get_role(m) == 'user':
            return [to_dict(m)]
    
    # If no user message, return all
    return [to_dict(m) for m in messages]


def should_reset_session(client, request: ChatCompletionRequest) -> bool:
    """
    Determine if we should reset the Gemini session.
    Only reset on timeout or if there's no active session.
    """
    global _last_request_time
    
    current_time = time.time()



    # if there aren't any messages role 'assistant', 'tool', or 'function', reset session
    for m in request.messages:
        role = m.role if hasattr(m, 'role') else m.get('role', '')
        if role in ('assistant', 'tool', 'function'):
            break
    else:
        # No assistant, tool, or function messages found, reset session
        print(f"[SESSION] No assistant/tool/function messages found, resetting session")
        return True


    # If timeout passed, reset
    if _last_request_time > 0 and (current_time - _last_request_time) > SESSION_TIMEOUT_SECONDS:
        print(f"[SESSION] Timeout of {SESSION_TIMEOUT_SECONDS}s reached, resetting session")
        return True
    
    # If no conversation_id, it's a new session anyway
    if not client.conversation_id:
        return True
    
    return False


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, authorization: str = Header(None)):

    print(f"\n")

    global _last_request_time
    verify_api_key(authorization)
    

    # debug raw request and all headers into a file log 
    with open("log_raw_requests.log", "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(request.model_dump(), ensure_ascii=False, indent=2))
        log_file.write("\n---\n")

    # Log request parameters (truncate image content)
    request_log = {
        "model": request.model,
        "stream": request.stream,
        "messages": [],
        "tools": [t.model_dump() for t in request.tools] if request.tools else None
    }
    for m in request.messages:
        msg_log = {"role": m.role}
        if isinstance(m.content, list):
            content_log = []
            for item in m.content:
                if item.get("type") == "image_url":
                    img_url = item.get("image_url", {})
                    if isinstance(img_url, dict):
                        url = img_url.get("url", "")
                    else:
                        url = str(img_url)
                    content_log.append({"type": "image_url", "url_preview": url[:100] + "..." if len(url) > 100 else url})
                else:
                    content_log.append(item)
            msg_log["content"] = content_log
        else:
            msg_log["content"] = m.content
        request_log["messages"].append(msg_log)
    
    try:
        client = get_client()

        # Check if we need to reset
        needs_reset = should_reset_session(client, request)
        
        # Detect if it's a tool call continuation
        # IMPORTANT: Only continuation if LAST message is tool/function
        # Not if there are old tool messages in history
        last_msg = request.messages[-1] if request.messages else None
        last_role = (last_msg.role if hasattr(last_msg, 'role') else last_msg.get('role', '')) if last_msg else ''
        is_tool_continuation = last_role in ('tool', 'function')
        
        if needs_reset:
            client.reset()
            # New session: send all messages to establish context
            messages = [{"role": m.role if hasattr(m, 'role') else m.get('role', ''),
                        "content": m.content if hasattr(m, 'content') else m.get('content', '')} 
                       for m in request.messages]
            print(f"[SESSION] New session started. Sending {len(messages)} message(s) to establish context")
        else:
            # Existing session: extract relevant messages
            messages = extract_last_user_message(request.messages)
            if is_tool_continuation:
                print(f"[SESSION] Tool call continuation (conv_id: {client.conversation_id[:20]}...). Sending tool results")
            else:
                print(f"[SESSION] Active session (conv_id: {client.conversation_id[:20]}...). Sending only last message")
        
        # Update timestamp
        _last_request_time = time.time()
        
        # If there are tools, add tool prompt directly to user message
        # IMPORTANT: Don't add tools_prompt in tool call continuations
        # because Gemini already has the context of available tools
        if request.tools and len(messages) > 0 and not is_tool_continuation:
            tools_prompt = build_tools_prompt([t.model_dump() for t in request.tools])
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "user":
                    original = messages[i]["content"]
                    if isinstance(original, str):
                        messages[i]["content"] = tools_prompt + original
                    break
        

        # dump messages to logs_messages.log for debugging
        with open("logs_messages.log", "a", encoding="utf-8") as msg_log_file:
            msg_log_file.write(json.dumps(messages, ensure_ascii=False, indent=2))
            msg_log_file.write("\n---\n")

        response = client.chat(messages=messages, model=request.model)
        
        reply_content = response.choices[0].message.content
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created_time = int(time.time())
        
        # Parse tool calls
        tool_calls = []
        final_content = reply_content
        if request.tools:
            tool_calls, final_content = parse_tool_calls(reply_content)
        
        # Handle streaming response
        if request.stream:
            async def generate_stream():
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                
                if tool_calls:
                    # Stream return tool calls
                    for tc in tool_calls:
                        chunk_data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": request.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"tool_calls": [tc]},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                else:
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": request.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": final_content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                
                chunk_data = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": request.model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "tool_calls" if tool_calls else "stop"
                    }]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(), 
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        
        # Build response message
        response_message = {"role": "assistant"}
        if tool_calls:
            response_message["content"] = final_content if final_content else None
            response_message["tool_calls"] = tool_calls
            finish_reason = "tool_calls"
        else:
            response_message["content"] = final_content
            finish_reason = "stop"
        
        response_data = ChatCompletionResponse(
            id=completion_id,
            created=created_time,
            model=request.model,
            choices=[ChatCompletionChoice(index=0, message=response_message, finish_reason=finish_reason)],
            usage=Usage(prompt_tokens=response.usage.prompt_tokens, completion_tokens=response.usage.completion_tokens, total_tokens=response.usage.total_tokens)
        )
        
        log_api_call(request_log, response_data.model_dump())
        
        return JSONResponse(
            content=response_data.model_dump(),
            headers={
                "Cache-Control": "no-cache",
                "X-Request-Id": completion_id,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"[ERROR] Chat error: {error_msg}")
        traceback.print_exc()
        log_api_call(request_log, None, error=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/v1/chat/completions/reset")
async def reset_context(authorization: str = Header(None)):
    verify_api_key(authorization)
    global _client
    if _client:
        _client.reset()
    return {"status": "ok"}


load_config()

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           Gemini OpenAI Compatible API Server            ║
╠══════════════════════════════════════════════════════════╣
║  Admin: http://localhost:{PORT}/admin                      ║
║  API URL: http://localhost:{PORT}/v1                       ║
║  API Key:  {API_KEY}                                ║
╚══════════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host=HOST, port=PORT)
