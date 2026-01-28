# Gemini Web官网 转 OpenAi API

基于 Gemini 网页版的逆向工程，提供 OpenAI 兼容 API 服务。

## ✨ 功能特性

- ✅ 文本对话
- ✅ 多轮对话（上下文保持）
- ✅ 图片识别（支持 base64 和 URL）
- ✅ **图片生成（自动下载高清无水印原图）** 🆕
- ✅ **视频生成（异步，需到官网查看）** 🆕
- ✅ 流式响应（Streaming）
- ✅ Tools / Function Calling 支持
- ✅ OpenAI SDK 完全兼容
- ✅ Web 后台配置界面
- ✅ 后台登录认证

## 📝 更新日志

### v1.2.0 (2026-01-04)
- 🆕 新增图片生成支持
  - AI 生成的图片自动下载到本地并通过代理返回
  - 自动获取高清无水印原图
  - 过滤用户上传的图片，只返回 AI 生成的内容
- 🆕 新增视频生成提示
  - 视频为异步生成，返回友好提示引导用户到官网查看
  - 显示使用限制说明
- 🔧 优化图片处理
  - 修复图片重复下载问题
  - 修复图片理解时返回上传图片 URL 的问题
  - 清理响应中的占位符 URL
- 📝 使用限制说明（官网限制）
  - 视频生成 (Veo 模型)：每天总共可以生成 3 次
  - 图片生成 (Nano Banana 模型)：每天总共可以生成 1000 次

### v1.1.0 (2025-12-26)
- 🆕 新增 Tools / Function Calling 支持
  - 支持 OpenAI 格式的 tools 参数
  - 自动解析工具调用并返回 tool_calls
  - 可对接 MCP 服务器使用

### v1.0.0
- 初始版本
- 支持文本对话、图片识别、流式响应
- Web 后台配置界面

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 启动服务

```bash
uv run server.py
```

启动后会显示：

```text
╔══════════════════════════════════════════════════════════╗
║           Gemini OpenAI Compatible API Server            ║
╠══════════════════════════════════════════════════════════╣
║  后台配置: http://localhost:8000/admin                   ║
║  API 地址: http://localhost:8000/v1                      ║
║  API Key:  sk-gemini                                     ║
╚══════════════════════════════════════════════════════════╝
```

### 3. 配置 Cookie

1. 打开后台管理页面 `http://localhost:8000/admin`
2. 使用默认账号登录：
   - 用户名: `admin`
   - 密码: `admin123`
3. 获取 Cookie：
   - 登录 [Gemini 网页版](https://gemini.google.com)
   - 按 `F12` 打开开发者工具
   - 切换到 `Application` 标签页
   - 左侧选择 `Cookies` → `https://gemini.google.com`
   - 右键任意 cookie → **Copy all as Header String**
4. 粘贴到后台配置页面的「Cookie 字符串」输入框，点击保存

> 💡 系统会自动解析 Cookie 并获取所需 Token（SNLM0E、PUSH_ID 等），无需手动填写

### 4. 配置模型 ID（可选）

如果发现模型切换不生效（例如选择 Pro 版但实际使用的是极速版），需要手动更新模型 ID：

**抓包获取模型 ID：**

1. 打开 [Gemini 网页版](https://gemini.google.com)，按 `F12` 打开开发者工具
2. 切换到 `Network` 标签页
3. 在 Gemini 网页中切换到目标模型（如 Pro 版），发送一条消息
4. 在 Network 中找到 `StreamGenerate` 请求
5. 查看请求头 `x-goog-ext-525001261-jspb`，格式如下：

   ```json
   [1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4],null,null,2]
   ```

6. 第 5 个元素（`e6fa609c3fa255c0`）即为该模型的 ID

**配置模型 ID：**

在后台管理页面的「模型 ID 配置」区域，将抓取到的 ID 填入对应输入框：

| 模型 | 默认 ID | 说明 |
|------|---------|------|
| 极速版 (Flash) | `56fdd199312815e2` | 响应最快 |
| Pro 版 | `e6fa609c3fa255c0` | 质量更高 |
| 思考版 (Thinking) | `e051ce1aa80aa576` | 深度推理 |

> ⚠️ Google 可能会更新模型 ID，如果模型切换失效请重新抓包获取最新 ID

### 5. 调用 API

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

- `gemini-3.0-flash` - 快速响应（极速版）
- `gemini-3.0-flash-thinking` - 思考模式
- `gemini-3.0-pro` - 专业版

### 模型切换

API 支持通过 `model` 参数切换不同版本的 Gemini：

```python
# 使用极速版
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "你好"}]
)

# 使用 Pro 版
response = client.chat.completions.create(
    model="gemini-3.0-pro",
    messages=[{"role": "user", "content": "你好"}]
)

# 使用思考版
response = client.chat.completions.create(
    model="gemini-3.0-flash-thinking",
    messages=[{"role": "user", "content": "你好"}]
)
```

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



### 本地图片（Base64）

```python
import base64
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

# 读取本地图片（使用项目中的 image.png 示例图片）
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

## 🔧 Tools / Function Calling

支持 OpenAI 格式的工具调用，可用于对接 MCP 服务器或自定义工具。

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-gemini")

# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "在数据库中搜索用户信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "用户名"}
                },
                "required": ["username"]
            }
        }
    }
]

# 调用 API
response = client.chat.completions.create(
    model="gemini-3.0-flash",
    messages=[{"role": "user", "content": "查询用户 zhangsan 的信息"}],
    tools=tools
)

# 检查工具调用
if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        print(f"调用工具: {tc.function.name}")
        print(f"参数: {tc.function.arguments}")
else:
    print(response.choices[0].message.content)
```

### 工具调用流程

1. 定义 tools 数组，描述可用工具
2. 发送请求时传入 tools 参数
3. 如果 AI 决定调用工具，返回 `tool_calls`
4. 执行工具获取结果
5. 将结果发回 AI 继续对话



## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | API 服务 + Web 后台 |
| `client.py` | Gemini 逆向客户端 |
| `api.py` | OpenAI 兼容封装 |
| `image.png` | 示例图片（用于测试图片识别） |
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

### Q: 模型切换不生效？

请参考上方「4. 配置模型 ID」章节，重新抓包获取最新的模型 ID 并更新配置。

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

所有 API 调用会记录到 `log_api.log` 文件。

## 📄 License

MIT
### 视频参考
https://www.bilibili.com/video/BV1ZWB4BNE9n/
## 🖼️ cookie获取示例

![示例图片](image.png)
