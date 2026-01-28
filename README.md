# Gemini Web to OpenAI API

Reverse engineering based on Gemini web version, providing OpenAI-compatible API service.

## ✨ Features

- ✅ Text chat
- ✅ Multi-turn conversations (context preservation)
- ✅ Image recognition (supports base64 and URL)
- ✅ **Image generation (auto-download HD watermark-free images)** 🆕
- ✅ **Video generation (async, check on official website)** 🆕
- ✅ Streaming response
- ✅ Tools / Function Calling support
- ✅ Full OpenAI SDK compatibility
- ✅ Web admin configuration interface
- ✅ Admin login authentication

## 📝 Changelog

### v1.2.0 (2026-01-04)
- 🆕 Added image generation support
  - AI-generated images automatically downloaded locally and returned via proxy
  - Auto-fetch HD watermark-free original images
  - Filter user-uploaded images, only return AI-generated content
- 🆕 Added video generation notifications
  - Videos are generated asynchronously, return friendly prompts to guide users to the official website
  - Display usage limitation explanations
- 🔧 Optimized image processing
  - Fixed image duplicate download issues
  - Fixed returning uploaded image URLs during image understanding
  - Cleaned placeholder URLs in responses
- 📝 Usage limitations explanation (official website restrictions)
  - Video generation (Veo model): 3 generations per day total
  - Image generation (Nano Banana model): 1000 generations per day total

### v1.1.0 (2025-12-26)
- 🆕 Added Tools / Function Calling support
  - Support OpenAI format tools parameters
  - Automatically parse tool calls and return tool_calls
  - Can connect to MCP servers

### v1.0.0
- Initial version
- Support text chat, image recognition, streaming response
- Web admin configuration interface

## 🚀 Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Start Service

```bash
uv run server.py
```

After starting, it will display:

```text
╔══════════════════════════════════════════════════════════╗
║           Gemini OpenAI Compatible API Server            ║
╠══════════════════════════════════════════════════════════╣
║  Admin Panel: http://localhost:8000/admin               ║
║  API URL: http://localhost:8000/v1                      ║
║  API Key:  sk-gemini                                    ║
╚══════════════════════════════════════════════════════════╝
```

### 3. Configure Cookie

1. Open admin panel `http://localhost:8000/admin`
2. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`
3. Get Cookie:
   - Login to [Gemini Web](https://gemini.google.com)
   - Press `F12` to open developer tools
   - Switch to `Application` tab
   - Select `Cookies` → `https://gemini.google.com` on the left
   - Right-click any cookie → **Copy all as Header String**
4. Paste into the "Cookie String" input box in admin panel, click save

> 💡 The system will automatically parse Cookie and get required tokens (SNLM0E, PUSH_ID, etc.), no manual input needed

### 4. Configure Model ID (Optional)

If you find model switching doesn't work (e.g., selected Pro version but actually using Flash version), you need to manually update model IDs:

**Capture Model ID:**

1. Open [Gemini Web](https://gemini.google.com), press `F12` to open developer tools
2. Switch to `Network` tab
3. In Gemini web, switch to target model (e.g., Pro version), send a message
4. Find `StreamGenerate` request in Network
5. Check request header `x-goog-ext-525001261-jspb`, format like:

   ```json
   [1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4],null,null,2]
   ```

6. The 5th element (`e6fa609c3fa255c0`) is the model ID

**Configure Model ID:**

In the admin panel "Model ID Configuration" section, fill the captured ID into corresponding input box:

| Model | Default ID | Description |
|-------|------------|-------------|
| Flash | `56fdd199312815e2` | Fastest response |
| Pro | `e6fa609c3fa255c0` | Higher quality |
| Thinking | `e051ce1aa80aa576` | Deep reasoning |

> ⚠️ Google may update model IDs, please re-capture latest IDs if model switching fails

### 5. Call API

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-gemini"
)

response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "Hello"}]
)
print(response.choices[0].message.content)
```

## 📡 API Information

| Item | Value |
|------|-------|
| Base URL | `http://localhost:8000/v1` |
| API Key | `sk-gemini` |
| Admin Panel | `http://localhost:8000/admin` |
| Login Credentials | `admin` / `admin123` |

### Available Models

- `gemini-3.0-flash` - Fast response (Flash version)
- `gemini-3.0-flash-thinking` - Thinking mode
- `gemini-3.0-pro` - Pro version

### Model Switching

API supports switching different versions of Gemini via `model` parameter:

```python
# Use Flash version
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "Hello"}]
)

# Use Pro version
response = client.chat.completions.create(
    model="gemini-3.0-pro",
    messages=[{"role": "user", "content": "Hello"}]
)

# Use Thinking version
response = client.chat.completions.create(
    model="gemini-3.0-flash-thinking",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## 💬 Multi-turn Conversation Example

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

messages = []

# First round
messages.append({"role": "user", "content": "My name is John, I'm a programmer"})
response = client.chat.completions.create(model="gemini-3.0-flash", messages=messages)
reply = response.choices[0].message.content
print(f"Assistant: {reply}")
messages.append({"role": "assistant", "content": reply})

# Second round (test context)
messages.append({"role": "user", "content": "What did I say my name was?"})
response = client.chat.completions.create(model="gemini-3.0-flash", messages=messages)
print(f"Assistant: {response.choices[0].message.content}")
# Output: You said your name was John
```



### Local Image (Base64)

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

# Read local image (using image.png example in project)
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
print(response.choices[0].message.content)
```

### Web Image (URL)

```python
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What animal is this?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
    }]
)
```

## 🌊 Streaming Response

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

stream = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "Write a poem about spring"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## 🔧 Tools / Function Calling

Supports OpenAI format tool calls, can be used to connect MCP servers or custom tools.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search user information in database",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Username"}
                },
                "required": ["username"]
            }
        }
    }
]

# Call API
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "Query user zhangsan's information"}],
    tools=tools
)

# Check tool calls
if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        print(f"Called tool: {tc.function.name}")
        print(f"Arguments: {tc.function.arguments}")
else:
    print(response.choices[0].message.content)
```

### Tool Call Flow

1. Define tools array, describe available tools
2. Pass tools parameter when sending request
3. If AI decides to call tools, returns `tool_calls`
4. Execute tools to get results
5. Send results back to AI to continue conversation



## 📁 File Description

| File | Description |
|------|-------------|
| `server.py` | API service + Web admin panel |
| `client.py` | Gemini reverse engineering client |
| `api.py` | OpenAI compatibility wrapper |
| `image.png` | Example image (for testing image recognition) |
| `config_data.json` | Runtime configuration (auto-generated) |

## ⚙️ Configuration

### Change Admin Credentials

Edit configuration at top of `server.py`:

```python
# Admin login credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "your_password"
```

### Change API Key

```python
API_KEY = "your-api-key"
```

### Change Port

```python
PORT = 8000
```

## ❓ FAQ

### Q: Token expired error?

Just paste Cookie again in admin panel, no need to restart service. Configuration takes effect immediately after saving.

### Q: Model switching doesn't work?

Please refer to section "4. Configure Model ID" above, re-capture latest model IDs and update configuration.

### Q: Image recognition failed?

1. Ensure Cookie is complete, system will auto-fetch PUSH_ID
2. If still failing, check if Cookie is expired
3. Ensure image format is correct (supports PNG, JPG, GIF, WebP)

### Q: Streaming response not working?

Ensure client supports SSE (Server-Sent Events), and set `stream=True`.

### Q: How to use in IDE plugins?

Configure OpenAI-compatible AI plugins:

- Base URL: `http://localhost:8000/v1`
- API Key: `sk-gemini`
- Model: `gemini-3.0-flash`

### Q: Multi-turn conversation context lost?

Ensure each request includes complete message history (messages array).

## 🔧 Development

### Debug Mode

Set `debug=True` in `get_client()` to view detailed request logs.

### API Logs

All API calls are logged to `api_logs.json` file.

## 📄 License

MIT

### Video Reference
https://www.bilibili.com/video/BV1ZWB4BNE9n/

## 🖼️ Cookie Acquisition Example

![Example Image](image.png)
