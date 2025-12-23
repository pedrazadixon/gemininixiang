# Gemini Web 逆向 API

基于 Gemini 网页版的逆向工程，提供 OpenAI 兼容 API 服务。

## ✨ 功能特性

- ✅ 文本对话
- ✅ 多轮对话（上下文保持）
- ✅ 图片识别（支持 base64 和 URL）
- ✅ 流式响应（Streaming）
- ✅ OpenAI SDK 完全兼容
- ✅ Web 后台配置界面
- ✅ 后台登录认证

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python server.py
```

启动后会显示：
```
╔══════════════════════════════════════════════════════════╗
║           Gemini OpenAI Compatible API Server            ║
╠══════════════════════════════════════════════════════════╣
║  后台配置: http://localhost:8000/admin                   ║
║  API 地址: http://localhost:8000/v1                      ║
║  API Key:  sk-gemini                                     ║
╚══════════════════════════════════════════════════════════╝
```

### 3. 配置 Cookie

1. 打开 http://localhost:8000/admin
2. 使用默认账号登录：
   - 用户名: `admin`
   - 密码: `admin123`
3. 获取 Cookie：
   - 登录 https://gemini.google.com
   - F12 → Application → Cookies
   - 右键任意 cookie → **Copy all as Header String**
4. 粘贴到后台配置页面，点击保存

> 💡 系统会自动解析 Cookie 并获取所需 Token，无需手动填写

### 4. 调用 API

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-gemini"
)

response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

## 📡 API 信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://localhost:8000/v1` |
| API Key | `sk-gemini` |
| 后台地址 | `http://localhost:8000/admin` |
| 登录账号 | `admin` / `admin123` |

### 可用模型

- `gemini-3.0-flash` - 快速响应
- `gemini-3.0-flash-thinking` - 思考模式
- `gemini-3.0-pro` - 专业版

## 💬 多轮对话示例

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

messages = []

# 第一轮
messages.append({"role": "user", "content": "我叫小明，是一名程序员"})
response = client.chat.completions.create(model="gemini-3.0-flash", messages=messages)
reply = response.choices[0].message.content
print(f"助手: {reply}")
messages.append({"role": "assistant", "content": reply})

# 第二轮（测试上下文）
messages.append({"role": "user", "content": "我刚才说我叫什么？"})
response = client.chat.completions.create(model="gemini-3.0-flash", messages=messages)
print(f"助手: {response.choices[0].message.content}")
# 输出: 你刚才说你叫小明
```

## 🖼️ 图片识别

### 本地图片（Base64）

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

# 读取本地图片
with open("image.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "请描述这张图片"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]
    }]
)
print(response.choices[0].message.content)
```

### 网络图片（URL）

```python
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "这是什么动物？"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
    }]
)
```

## 🌊 流式响应

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

stream = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "写一首关于春天的诗"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## 🎮 完整演示

运行交互式演示程序：

```bash
python demo_chat.py
```

演示包含：
1. 基础文本对话
2. 多轮对话（上下文保持）
3. 图片识别（网络图片）
4. 多轮对话 + 图片识别
5. 本地图片识别
6. 交互式对话

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | API 服务 + Web 后台 |
| `client.py` | Gemini 逆向客户端 |
| `demo_chat.py` | 完整演示程序 |
| `api.py` | OpenAI 兼容封装 |
| `config.example.py` | 配置模板 |
| `config_data.json` | 运行时配置（自动生成） |

## ⚙️ 配置说明

### 修改后台账号密码

编辑 `server.py` 顶部配置：

```python
# 后台登录账号密码
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "your_password"
```

### 修改 API Key

```python
API_KEY = "your-api-key"
```

### 修改端口

```python
PORT = 8000
```

## ❓ 常见问题

### Q: 提示 Token 过期？

重新在后台粘贴 Cookie 即可，无需重启服务。配置保存后立即生效。

### Q: 图片识别失败？

1. 确保 Cookie 完整，系统会自动获取 PUSH_ID
2. 如果仍失败，检查 Cookie 是否过期
3. 确保图片格式正确（支持 PNG、JPG、GIF、WebP）

### Q: 流式响应不工作？

确保客户端支持 SSE（Server-Sent Events），并设置 `stream=True`。

### Q: 如何在 IDE 插件中使用？

配置 OpenAI 兼容的 AI 插件：
- Base URL: `http://localhost:8000/v1`
- API Key: `sk-gemini`
- Model: `gemini-3.0-flash`

### Q: 多轮对话上下文丢失？

确保每次请求都包含完整的消息历史（messages 数组）。

## 🔧 开发

### 调试模式

在 `get_client()` 中设置 `debug=True` 可查看详细请求日志。

### API 日志

所有 API 调用会记录到 `api_logs.json` 文件。

## 📄 License

MIT
### 视频参考
https://www.bilibili.com/video/BV1ZWB4BNE9n/
