"""
Gemini Web Reverse Engineering Client
Supports text and image requests, contextual dialogue, and OpenAI format input/output.
Manual token configuration, no code login required
"""

import re
import json
import random
import string
import base64
import uuid
import httpx
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import time


class CookieExpiredError(Exception):
    """Cookie expired or invalid exception"""
    pass


class ImageUploadError(Exception):
    """Image upload failed exception"""
    pass


@dataclass
class Message:
    """OpenAI format message"""
    role: str
    content: Union[str, List[Dict[str, Any]]]


@dataclass
class ChatCompletionChoice:
    index: int
    message: Message
    finish_reason: str = "stop"


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionResponse:
    """OpenAI format response"""
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str = "gemini-web"
    choices: List[ChatCompletionChoice] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {"role": c.message.role, "content": c.message.content},
                    "finish_reason": c.finish_reason
                }
                for c in self.choices
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens
            }
        }


class GeminiClient:
    """
    Gemini Web Reverse Engineering Client
    
    Usage:
    1. Open https://gemini.google.com and log in
    2. Press F12 to open Developer Tools -> Application -> Cookies
    3. Copy the following cookie values:
       - __Secure-1PSID
       - __Secure-1PSIDTS (optional)
    4. Network tab -> Find any request -> Copy SNlM0e value (search in page source)
    """
    
    BASE_URL = "https://gemini.google.com"
    
    def __init__(
        self,
        secure_1psid: str,
        secure_1psidts: str = None,
        secure_1psidcc: str = None,
        snlm0e: str = None,
        bl: str = None,
        cookies_str: str = None,
        push_id: str = None,
        model_ids: dict = None,
        debug: bool = False,
        media_base_url: str = None,
    ):
        """
        Initialize client - manual token configuration
        
        Args:
            secure_1psid: __Secure-1PSID cookie (required)
            secure_1psidts: __Secure-1PSIDTS cookie (recommended)
            secure_1psidcc: __Secure-1PSIDCC cookie (recommended)
            snlm0e: SNlM0e token (required, obtained from page source)
            bl: BL version number (optional, auto-fetch)
            cookies_str: Full cookie string (optional, alternative to individual settings)
            push_id: Push ID for image upload (required for image upload)
            model_ids: Model ID mapping {"flash": "xxx", "pro": "xxx", "thinking": "xxx"}
            debug: Whether to print debug information
            media_base_url: Base URL for media files (e.g., http://localhost:8000), used to construct full media access URLs
        """
        self.secure_1psid = secure_1psid
        self.secure_1psidts = secure_1psidts
        self.secure_1psidcc = secure_1psidcc
        self.snlm0e = snlm0e
        self.bl = bl
        self.push_id = push_id
        self.debug = debug
        self.media_base_url = media_base_url or ""
        
        # Model ID mapping (used for selecting model in request headers)
        self.model_ids = model_ids or {
            "flash": "56fdd199312815e2",
            "pro": "e6fa609c3fa255c0",
            "thinking": "e051ce1aa80aa576",
        }
        
        self.session = httpx.Client(
            timeout=1220.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        
        # Set cookies
        if cookies_str:
            self._set_cookies_from_string(cookies_str)
        else:
            self.session.cookies.set("__Secure-1PSID", secure_1psid, domain=".google.com")
            if secure_1psidts:
                self.session.cookies.set("__Secure-1PSIDTS", secure_1psidts, domain=".google.com")
            if secure_1psidcc:
                self.session.cookies.set("__Secure-1PSIDCC", secure_1psidcc, domain=".google.com")
        
        # Session context
        self.conversation_id: str = ""
        self.response_id: str = ""
        self.choice_id: str = ""
        self.request_count: int = 0
        
        # Message history
        self.messages: List[Message] = []
        
        # Validate required parameters
        if not self.snlm0e:
            raise ValueError(
                "SNlM0e is a required parameter!\n"
                "How to obtain:\n"
                "1. Open https://gemini.google.com and log in\n"
                "2. F12 -> View page source (Ctrl+U)\n"
                "3. Search for 'SNlM0e' to find something like: \"SNlM0e\":\"xxxxxx\"\n"
                "4. Copy the value inside the quotes"
            )
        
        # Auto-fetch BL
        if not self.bl:
            self._fetch_bl()
    
    def _set_cookies_from_string(self, cookies_str: str):
        """Parse from full cookie string"""
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                self.session.cookies.set(key.strip(), value.strip(), domain=".google.com")
    
    def _fetch_bl(self):
        """Fetch BL version number"""
        try:
            resp = self.session.get(self.BASE_URL)
            match = re.search(r'"cfb2h":"([^"]+)"', resp.text)
            if match:
                self.bl = match.group(1)
            else:
                # Use default value
                self.bl = "boq_assistant-bard-web-server_20241209.00_p0"
            if self.debug:
                print(f"[DEBUG] BL: {self.bl}")
        except Exception as e:
            self.bl = "boq_assistant-bard-web-server_20241209.00_p0"
            if self.debug:
                print(f"[DEBUG] Failed to fetch BL, using default: {e}")


    
    def _parse_content(self, content: Union[str, List[Dict]]) -> tuple:
        """Parse OpenAI format content, return (text, images)"""
        if isinstance(content, str):
            return content, []
        
        text_parts = []
        images = []
        
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "image_url":
                # Support two formats: {"url": "..."} or direct string
                image_url_data = item.get("image_url", {})
                if isinstance(image_url_data, str):
                    url = image_url_data
                else:
                    url = image_url_data.get("url", "")
                
                if not url:
                    continue
                    
                if url.startswith("data:"):
                    # base64 format: data:image/png;base64,xxxxx
                    match = re.match(r'data:([^;]+);base64,(.+)', url)
                    if match:
                        images.append({"mime_type": match.group(1), "data": match.group(2)})
                elif url.startswith("http://") or url.startswith("https://"):
                    # URL format, download image
                    try:
                        resp = httpx.get(url, timeout=30)
                        if resp.status_code == 200:
                            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                            images.append({"mime_type": mime, "data": base64.b64encode(resp.content).decode()})
                    except Exception as e:
                        if self.debug:
                            print(f"[DEBUG] Failed to download image: {e}")
                else:
                    # Might be a pure base64 string (without data: prefix)
                    try:
                        # Try decoding to verify if it's valid base64
                        base64.b64decode(url[:100])  # Only verify the first 100 characters
                        images.append({"mime_type": "image/png", "data": url})
                    except:
                        pass
        
        return " ".join(text_parts) if text_parts else "", images
    
    def _upload_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """
        Upload image to Gemini server
        
        Args:
            image_data: Image binary data
            mime_type: Image MIME type
            
        Returns:
            str: Uploaded image path (with token)
        """
        if not self.push_id:
            raise CookieExpiredError(
                "Image upload requires push_id\n"
                "How to get it: run python get_push_id.py or get it from browser Network"
            )
        
        try:
            upload_url = "https://push.clients6.google.com/upload/"
            filename = f"image_{random.randint(100000, 999999)}.png"
            
            # Headers required by browser
            browser_headers = {
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
                "origin": "https://gemini.google.com",
                "referer": "https://gemini.google.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "x-browser-channel": "stable",
                "x-browser-copyright": "Copyright 2025 Google LLC. All Rights reserved.",
                "x-browser-validation": "Aj9fzfu+SaGLBY9Oqr3S7RokOtM=",
                "x-browser-year": "2025",
                "x-client-data": "CIa2yQEIpbbJAQipncoBCNvaygEIk6HLAQiFoM0BCJaMzwEIkZHPAQiSpM8BGOyFzwEYsobPAQ==",
            }
            
            # Step 1: Get upload_id
            init_headers = {
                **browser_headers,
                "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                "push-id": self.push_id,
                "x-goog-upload-command": "start",
                "x-goog-upload-header-content-length": str(len(image_data)),
                "x-goog-upload-protocol": "resumable",
                "x-tenant-id": "bard-storage",
            }
            
            init_resp = self.session.post(upload_url, data={"File name": filename}, headers=init_headers)
            
            if self.debug:
                print(f"[DEBUG] Initialize upload status: {init_resp.status_code}")
            
            # Check initialization response status
            if init_resp.status_code == 401 or init_resp.status_code == 403:
                raise CookieExpiredError(
                    f"Cookie expired or invalid (HTTP {init_resp.status_code})\n"
                    "Please re-acquire the following information:\n"
                    "1. __Secure-1PSID\n"
                    "2. __Secure-1PSIDTS\n"
                    "3. SNlM0e\n"
                    "4. push_id"
                )
            
            upload_id = init_resp.headers.get("x-guploader-uploadid")
            if not upload_id:
                raise CookieExpiredError(
                    f"Failed to get upload_id (status code: {init_resp.status_code})\n"
                    "Possible reason: Cookie expired, please re-acquire all tokens"
                )
            
            if self.debug:
                print(f"[DEBUG] Upload ID: {upload_id[:50]}...")
            
            # Step 2: Upload image data
            final_upload_url = f"{upload_url}?upload_id={upload_id}&upload_protocol=resumable"
            
            upload_headers = {
                **browser_headers,
                "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                "push-id": self.push_id,
                "x-goog-upload-command": "upload, finalize",
                "x-goog-upload-offset": "0",
                "x-tenant-id": "bard-storage",
                "x-client-pctx": "CgcSBWjK7pYx",
            }
            
            upload_resp = self.session.post(
                final_upload_url,
                headers=upload_headers,
                content=image_data
            )
            
            if self.debug:
                print(f"[DEBUG] Upload data status: {upload_resp.status_code}")
                print(f"[DEBUG] Response headers: {dict(upload_resp.headers)}")
                print(f"[DEBUG] Full response content: {upload_resp.text}")
            
            # Check upload response status
            if upload_resp.status_code == 401 or upload_resp.status_code == 403:
                raise CookieExpiredError(
                    f"Image upload authentication failed (HTTP {upload_resp.status_code})\n"
                    "Cookie expired, please re-acquire"
                )
            
            if upload_resp.status_code != 200:
                raise Exception(f"Image data upload failed: {upload_resp.status_code}, Response: {upload_resp.text[:200] if upload_resp.text else '(empty)'}")
            
            # Extract image path from response
            response_text = upload_resp.text
            image_path = None
            
            # Try to parse JSON
            try:
                response_json = json.loads(response_text)
                image_path = self._extract_image_path(response_json)
            except json.JSONDecodeError:
                # If not JSON, try to extract path from text
                match = re.search(r'/contrib_service/[^\s"\']+', response_text)
                if match:
                    image_path = match.group(0)
            
            # Verify image path integrity
            if not image_path:
                raise CookieExpiredError(
                    f"Failed to extract image path from response\n"
                    f"Response content: {response_text[:300]}\n"
                    "Possible reason: Cookie expired, please re-acquire all tokens"
                )
            
            # Check if path is valid (length is sufficient, new version may not have query parameters)
            if "/contrib_service/" in image_path:
                # Path length must be sufficiently long to be valid
                if len(image_path) < 40:
                    raise CookieExpiredError(
                        f"Image path is incomplete\n"
                        f"Returned path: {image_path}\n"
                        "Reason: Cookie expired or insufficient permissions\n"
                        "Solution:\n"
                        "1. Re-login at https://gemini.google.com\n"
                        "2. Update all tokens in config.py:\n"
                        "   - SECURE_1PSID\n"
                        "   - SECURE_1PSIDTS\n"
                        "   - SNLM0E\n"
                        "   - PUSH_ID"
                    )
            
            if self.debug:
                print(f"[DEBUG] Image path: {image_path}")
            
            return image_path
            
        except CookieExpiredError:
            raise
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Upload failed: {e}")
            raise Exception(f"Image upload failed: {e}")
    
    def _extract_image_path(self, data: Any) -> str:
        """Recursively extract image path from response data"""
        if isinstance(data, str):
            if data.startswith("/contrib_service/"):
                return data
        elif isinstance(data, dict):
            for value in data.values():
                result = self._extract_image_path(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._extract_image_path(item)
                if result:
                    return result
        return None
    
    def _build_request_data(self, text: str, images: List[Dict] = None, image_paths: List[str] = None, model: str = None) -> str:
        """Build request data - based on real request format"""
        # Session context (empty string means new conversation)
        conv_id = self.conversation_id or ""
        resp_id = self.response_id or ""
        choice_id = self.choice_id or ""
        
        # Process image data - format: [[[path, 1, null, mime_type], filename]]
        image_data = None
        if image_paths and len(image_paths) > 0:
            path = image_paths[0]
            mime_type = images[0]["mime_type"] if images else "image/png"
            filename = f"image_{random.randint(100000, 999999)}.png"
            # Build image array structure
            image_data = [[[path, 1, None, mime_type], filename]]
        
        # Generate unique session ID
        session_id = str(uuid.uuid4()).upper()
        timestamp = int(time.time() * 1000)
        
        # Model mapping: convert model name to Gemini internal model identifier
        # [[0]] = gemini-3.0-pro (Pro version)
        # [[1]] = gemini-3.0-flash (Flash version, default)
        # [[3]] = gemini-3.0-flash-thinking (Thinking version)
        model_code = [[1]]  # Default flash version
        if model:
            model_lower = model.lower()
            if "pro" in model_lower:
                model_code = [[0]]  # Pro version
            elif "thinking" in model_lower or "think" in model_lower:
                model_code = [[3]]  # Thinking version
            # flash or other cases keep default [[1]]
        
        # Build internal JSON array (based on real request format)
        # First element: [text, 0, null, image_data, null, null, 0]
        inner_data = [
            [text, 0, None, image_data, None, None, 0],
            ["zh-CN"],
            [conv_id, resp_id, choice_id, None, None, None, None, None, None, ""],
            self.snlm0e,
            None,  # Previously "test123", changed to null
            None,
            [1],
            1,
            None,
            None,
            1,
            0,
            None,
            None,
            None,
            None,
            None,
            model_code,  # Model selection field
            0,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            1,
            None,
            None,
            [4],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            [1],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            None,
            None,
            None,
            None,
            None,
            session_id,
            None,
            [],
            None,
            None,
            None,
            None,
            [timestamp // 1000, (timestamp % 1000) * 1000000]
        ]
        
        # Serialize to JSON string
        inner_json = json.dumps(inner_data, ensure_ascii=False, separators=(',', ':'))
        
        # Outer wrapping
        outer_data = [None, inner_json]
        f_req_value = json.dumps(outer_data, ensure_ascii=False, separators=(',', ':'))
        
        return f_req_value

    
    def _parse_response(self, response_text: str) -> str:
        """Parse response text - fixed version"""
        try:
            # Skip prefix and parse line by line
            lines = response_text.split("\n")
            final_text = ""
            generated_images_set = set()  # Use set for global deduplication
            last_inner_json = None  # Store the last valid inner_json for debugging
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith(")]}'"):
                    continue
                
                # Skip numeric lines (length markers)
                if line.isdigit():
                    continue
                
                try:
                    data = json.loads(line)
                    # data is a nested array, data[0] is the actual data
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        actual_data = data[0]
                        # Check if it's a wrb.fr response
                        if len(actual_data) >= 3 and actual_data[0] == "wrb.fr" and actual_data[2]:
                            inner_json = json.loads(actual_data[2])
                            last_inner_json = inner_json
                            
                            # Try to extract generated image URLs and merge into global set for deduplication
                            imgs = self._extract_generated_images(inner_json)
                            if imgs:
                                for img in imgs:
                                    generated_images_set.add(img)
                                if self.debug:
                                    print(f"[DEBUG] Extracted {len(imgs)} image URLs from response, current total: {len(generated_images_set)}")
                            
                            # Extract text content
                            if inner_json and len(inner_json) > 4 and inner_json[4]:
                                candidates = inner_json[4]
                                if candidates and len(candidates) > 0:
                                    candidate = candidates[0]
                                    if candidate and len(candidate) > 1 and candidate[1]:
                                        # candidate[1] is an array, the first element is text
                                        text = candidate[1][0] if isinstance(candidate[1], list) else candidate[1]
                                        if isinstance(text, str) and len(text) > len(final_text):
                                            final_text = text
                                            # Update conversation context
                                            if len(inner_json) > 1 and inner_json[1]:
                                                if isinstance(inner_json[1], list):
                                                    if len(inner_json[1]) > 0:
                                                        self.conversation_id = inner_json[1][0] or self.conversation_id
                                                    if len(inner_json[1]) > 1:
                                                        self.response_id = inner_json[1][1] or self.response_id
                                            if len(candidate) > 0:
                                                self.choice_id = candidate[0] or self.choice_id
                except Exception as e:
                    if self.debug:
                        print(f"[DEBUG] Error parsing line: {e}")
                    continue
            
            # Convert to list
            generated_images = list(generated_images_set)
            
            if self.debug:
                print(f"[DEBUG] Parsing completed: final_text length={len(final_text)}, number of images={len(generated_images)}")
            
            # Process generated images/videos - download and cache locally
            if generated_images:
                if self.debug:
                    print(f"[DEBUG] Extracted {len(generated_images)} media URLs, starting download...")
                
                # Download images and get local proxy URLs
                local_media_urls = []
                for i, url in enumerate(generated_images):
                    if self.debug:
                        print(f"[DEBUG] Downloading media {i+1}/{len(generated_images)}: {url[:80]}...")
                    local_url = self._download_media_as_data_url(url)
                    if local_url:
                        local_media_urls.append(local_url)
                        if self.debug:
                            print(f"[DEBUG] Media {i+1} downloaded successfully: {local_url}")
                    else:
                        # Download failed, use original URL
                        local_media_urls.append(url)
                        if self.debug:
                            print(f"[DEBUG] Media {i+1} download failed, using original URL")
                
                # Check for placeholders (if there is text)
                has_placeholder = False
                if final_text:
                    has_placeholder = ('image_generation_content' in final_text or 
                                       'video_gen_chip' in final_text)
                
                # Construct response with local proxy URLs
                media_parts = []
                for i, url in enumerate(local_media_urls):
                    media_parts.append(f"![Generated content {i+1}]({url})")
                
                media_text = "\n\n".join(media_parts)
                
                if has_placeholder:
                    # Remove placeholder URLs
                    cleaned_text = re.sub(r'https?://googleusercontent\.com/(?:image_generation_content|video_gen_chip)/\d+', '', final_text)
                    cleaned_text = re.sub(r'http://googleusercontent\.com/(?:image_generation_content|video_gen_chip)/\d+', '', cleaned_text)
                    cleaned_text = re.sub(r'!\[.*?\]\(\)', '', cleaned_text)  # Remove empty image tags
                    cleaned_text = cleaned_text.strip()
                    if cleaned_text:
                        final_text = cleaned_text + "\n\n" + media_text
                    else:
                        final_text = media_text
                elif final_text:
                    # Text exists but no placeholders, append images
                    final_text = final_text + "\n\n" + media_text
                else:
                    # No text, only images
                    final_text = media_text
                
                if self.debug:
                    print(f"[DEBUG] Media processing completed, successfully downloaded {len([u for u in local_media_urls if u.startswith('/media/')])} items")
            
            # Check for video generation placeholders and replace with notice
            is_video_generation = False
            if final_text and 'video_gen_chip' in final_text:
                is_video_generation = True
            
            # Clean placeholder URLs and user-uploaded image URLs in the text
            if final_text:
                # Clean placeholder URLs
                final_text = re.sub(r'https?://googleusercontent\.com/(?:image_generation_content|video_gen_chip)/\d+\s*', '', final_text)
                final_text = re.sub(r'http://googleusercontent\.com/(?:image_generation_content|video_gen_chip)/\d+\s*', '', final_text)
                # Clean user-uploaded image URLs (/gg/ path, not /gg-dl/)
                final_text = re.sub(r'!\[[^\]]*\]\(https://[^)]*googleusercontent\.com/gg/[^)]+\)', '', final_text)
                final_text = re.sub(r'https://lh3\.googleusercontent\.com/gg/[^\s\)]+', '', final_text)
                final_text = final_text.strip()
            
            # If it is video generation, add a notice
            if is_video_generation:
                video_notice = "\n\n---\n📹 Video is generated asynchronously. The results can be viewed and downloaded in the official chat window.\n\n⏱️ Usage limits:\n- Video generation (Veo model): 3 times per day in total\n- Image generation (Nano Banana model): 1000 times per day in total"
                if final_text:
                    final_text = final_text + video_notice
                else:
                    final_text = video_notice.strip()
            
            if final_text:
                # Optimize image URLs to original high-definition size (only for original URLs that have not been downloaded)
                final_text = self._optimize_image_urls(final_text)
                return final_text
            
            # If there is no text and no images, try to extract more information from last_inner_json
            if self.debug and last_inner_json:
                print(f"[DEBUG] Unable to extract content, inner_json structure: {str(last_inner_json)[:500]}...")
                
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Parsing error: {e}")
        
        return "Unable to parse response"
    
    def _extract_generated_media(self, data: Any, depth: int = 0) -> List[str]:
        """Recursively extract generated image/video URLs from response data
        
        Gemini returns two media items (one with watermark and one without), we only keep the last one (without watermark)
        Only extract AI-generated media (/gg-dl/ path), do not extract user-uploaded images (/gg/ path)
        """
        if depth > 30:  # Prevent infinite recursion
            return []
        
        media_urls = []
        
        if isinstance(data, list):
            # Check if it is a media pair structure: [[null, 1, "file1.png/mp4", "url1", ...], null, null, [null, 1, "file2.png/mp4", "url2", ...]]
            # The first one has a watermark, the second one does not
            if (len(data) >= 1 and 
                isinstance(data[0], list) and len(data[0]) >= 4 and
                data[0][0] is None and 
                isinstance(data[0][1], int) and
                isinstance(data[0][2], str) and
                isinstance(data[0][3], str) and 
                data[0][3].startswith('https://') and
                'gg-dl/' in data[0][3]):  # Only match AI-generated media
                # Try to find the second media (without watermark)
                second_url = None
                if len(data) >= 4 and isinstance(data[3], list) and len(data[3]) >= 4:
                    if (data[3][0] is None and 
                        isinstance(data[3][3], str) and 
                        'gg-dl/' in data[3][3]):
                        second_url = data[3][3]
                
                # Prefer the second one, otherwise use the first one
                url = second_url if second_url else data[0][3]
                if 'image_generation_content' not in url and 'video_gen_chip' not in url:
                    media_urls.append(url)
                    return media_urls
            
            # Check if it is a single media data structure: [null, 1, "filename.png/mp4", "https://...gg-dl/..."]
            if (len(data) >= 4 and 
                data[0] is None and 
                isinstance(data[1], int) and
                isinstance(data[2], str) and 
                isinstance(data[3], str) and 
                data[3].startswith('https://') and
                'gg-dl/' in data[3]):  # Only match AI-generated media
                url = data[3]
                if 'image_generation_content' not in url and 'video_gen_chip' not in url:
                    media_urls.append(url)
                    return media_urls
            
            # Recursively search and collect all media URLs
            all_found = []
            for item in data:
                found = self._extract_generated_media(item, depth + 1)
                if found:
                    all_found.extend(found)
            
            # If multiple are found, return the last one (usually without watermark)
            if all_found:
                seen = set()
                unique = []
                for u in all_found:
                    if u not in seen:
                        seen.add(u)
                        unique.append(u)
                # Return the last one (without watermark)
                return [unique[-1]] if unique else []
                
        elif isinstance(data, dict):
            for value in data.values():
                found = self._extract_generated_media(value, depth + 1)
                if found:
                    return found
        
        return media_urls
    
    # Maintain backward compatibility
    def _extract_generated_images(self, data: Any, depth: int = 0) -> List[str]:
        """Alias for backward compatibility"""
        return self._extract_generated_media(data, depth)
    
    def _download_media_as_data_url(self, url: str) -> str:
        """Download media file and save to local cache, return local proxy URL
        
        Args:
            url: Media file URL
            
        Returns:
            str: Local proxy URL or base64 data URL
                 Returns an empty string if the download fails
        """
        try:
            # First optimize URL to get high-definition original image (images only)
            if ("googleusercontent" in url or "ggpht" in url) and not any(ext in url.lower() for ext in ['.mp4', '.webm', 'video']):
                # Remove existing size parameters, add original size parameter =s0
                url = re.sub(r'=w\d+(-h\d+)?(-[a-zA-Z]+)*$', '=s0', url)
                url = re.sub(r'=s\d+(-[a-zA-Z]+)*$', '=s0', url)
                url = re.sub(r'=h\d+(-[a-zA-Z]+)*$', '=s0', url)
                # If URL has no size parameter, add =s0
                if not url.endswith('=s0') and '=' not in url.split('/')[-1]:
                    url += '=s0'
            
            if self.debug:
                print(f"[DEBUG] Downloading media (HD): {url[:100]}...")
            
            # Use current session to download (with authenticated cookies)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://gemini.google.com/",
            }
            resp = self.session.get(url, timeout=60.0, headers=headers)
            
            if self.debug:
                print(f"[DEBUG] Download status: {resp.status_code}, size: {len(resp.content)} bytes")
            
            if resp.status_code != 200:
                if self.debug:
                    print(f"[DEBUG] Download media failed: HTTP {resp.status_code}")
                return ""
            
            # Check if content is empty or too small (possibly an error page)
            if len(resp.content) < 100:
                if self.debug:
                    print(f"[DEBUG] Downloaded content too small, possibly an error: {resp.content[:100]}")
                return ""
            
            # Detect file type based on content
            content = resp.content
            if content[:8] == b'\x89PNG\r\n\x1a\n':
                ext = ".png"
                mime = "image/png"
            elif content[:3] == b'\xff\xd8\xff':
                ext = ".jpg"
                mime = "image/jpeg"
            elif content[:6] in (b'GIF87a', b'GIF89a'):
                ext = ".gif"
                mime = "image/gif"
            elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
                ext = ".webp"
                mime = "image/webp"
            elif content[4:8] == b'ftyp' or content[:4] == b'\x00\x00\x00\x1c':
                ext = ".mp4"
                mime = "video/mp4"
            else:
                ext = ".png"
                mime = "image/png"
            
            # Generate unique filename
            import os
            media_id = f"gen_{uuid.uuid4().hex[:16]}"
            
            # Save to cache directory
            cache_dir = os.path.join(os.path.dirname(__file__), "media_cache")
            os.makedirs(cache_dir, exist_ok=True)
            file_path = os.path.join(cache_dir, media_id + ext)
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            if self.debug:
                print(f"[DEBUG] Media saved: {file_path}")
            
            # Return full media access URL
            media_path = f"/media/{media_id}"
            if self.media_base_url:
                return f"{self.media_base_url}{media_path}"
            return media_path
            
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Download media exception: {e}")
            return ""
    
    def _optimize_image_urls(self, text: str) -> str:
        """Optimize Google image URLs in text to original high-definition size
        
        Google image URL parameter explanation:
        - =w400 or =h400: specify width or height
        - =s400: specify maximum side length
        - =s0 or =w0-h0: original size
        """
        import re
        
        def optimize_url(url: str) -> str:
            # Match googleusercontent or ggpht image URLs
            if "googleusercontent" not in url and "ggpht" not in url:
                return url
            # Remove existing size parameters and add original size parameter
            url = re.sub(r'=w\d+(-h\d+)?(-[a-zA-Z]+)*$', '=s0', url)
            url = re.sub(r'=s\d+(-[a-zA-Z]+)*$', '=s0', url)
            url = re.sub(r'=h\d+(-[a-zA-Z]+)*$', '=s0', url)
            # If URL has no size parameter, add =s0
            if not url.endswith('=s0') and '=' not in url.split('/')[-1]:
                url += '=s0'
            return url
        
        # Match Markdown image syntax and plain URLs
        # Markdown: ![alt](url)
        def replace_md_img(match):
            alt = match.group(1)
            url = match.group(2)
            return f"![{alt}]({optimize_url(url)})"
        
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_md_img, text)
        
        # Match standalone Google image URLs
        def replace_url(match):
            return optimize_url(match.group(0))
        
        text = re.sub(r'https?://[^\s\)]+(?:googleusercontent|ggpht)[^\s\)]*', replace_url, text)
        
        return text

    
    def _extract_text(self, parsed_data: list) -> str:
        """Extract text from parsed data"""
        try:
            # Update conversation context
            if parsed_data and len(parsed_data) > 1:
                if parsed_data[1] and len(parsed_data[1]) > 0:
                    self.conversation_id = parsed_data[1][0] or self.conversation_id
                if parsed_data[1] and len(parsed_data[1]) > 1:
                    self.response_id = parsed_data[1][1] or self.response_id
            
            # Extract candidate replies
            if parsed_data and len(parsed_data) > 4 and parsed_data[4]:
                candidates = parsed_data[4]
                if candidates and len(candidates) > 0:
                    first_candidate = candidates[0]
                    if first_candidate and len(first_candidate) > 1:
                        self.choice_id = first_candidate[0] or self.choice_id
                        content_parts = first_candidate[1]
                        if content_parts and len(content_parts) > 0:
                            return content_parts[0] if isinstance(content_parts[0], str) else str(content_parts[0])
            
            # Fallback extraction
            if parsed_data and len(parsed_data) > 0:
                def find_text(obj, depth=0):
                    if depth > 10:
                        return None
                    if isinstance(obj, str) and len(obj) > 50:
                        return obj
                    if isinstance(obj, list):
                        for item in obj:
                            result = find_text(item, depth + 1)
                            if result:
                                return result
                    return None
                
                text = find_text(parsed_data)
                if text:
                    return text
                    
        except Exception as e:
            pass
        
        return "Unable to extract reply content"
    
    def chat(
        self,
        messages: List[Dict[str, Any]] = None,
        message: str = None,
        image: bytes = None,
        image_url: str = None,
        reset_context: bool = False,
        model: str = None
    ) -> ChatCompletionResponse:
        """
        Send chat request (OpenAI compatible format)
        
        Args:
            messages: List of messages in OpenAI format
            message: Simple text message (mutually exclusive with messages)
            image: Image binary data
            image_url: Image URL
            reset_context: Whether to reset context
            model: Model name (gemini-3.0-flash/gemini-3.0-flash-thinking/gemini-3.0-pro)
        
        Returns:
            ChatCompletionResponse: OpenAI format response
        """
        if reset_context:
            self.reset()
        
        # Process input
        text_parts = []
        images = []
        
        if messages:
            # OpenAI format message processing
            # If there is an existing conversation context (conversation_id is not empty), it means Gemini already has history
            # In this case, only user messages need to be processed, and assistant messages do not need to be sent again
            has_context = bool(self.conversation_id)
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "user":
                    t, imgs = self._parse_content(content)
                    if t:
                        text_parts.append(t)
                    if imgs:
                        images.extend(imgs)
                elif role == "assistant":
                    # Only include assistant messages if there is no Gemini context
                    # Otherwise, Gemini already knows these replies
                    if not has_context and isinstance(content, str) and content:
                        text_parts.append(f"[Previous response]: {content}")
                elif role == "system":
                    # system messages as pre-instructions (always needed)
                    if isinstance(content, str) and content:
                        text_parts.insert(0, content)
                
                self.messages.append(Message(role=role, content=content))
            
            text = "\n\n".join(text_parts)
        elif message:
            text = message
            self.messages.append(Message(role="user", content=message))
            
            if image:
                images = [{"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}]
            elif image_url:
                if image_url.startswith("data:"):
                    match = re.match(r'data:([^;]+);base64,(.+)', image_url)
                    if match:
                        images = [{"mime_type": match.group(1), "data": match.group(2)}]
                else:
                    try:
                        resp = httpx.get(image_url, timeout=30)
                        mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                        images = [{"mime_type": mime, "data": base64.b64encode(resp.content).decode()}]
                    except:
                        pass
        else:
            text = ""
        
        if not text:
            raise ValueError("Message content cannot be empty")
        
        # Send request
        return self._send_request(text, images, model)

    
    def _log_gemini_call(self, request_data: dict, response_text: str, error: str = None):
        """Log Gemini internal call"""
        import datetime
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "gemini_internal",
            "request": request_data,
            "response_raw": response_text,
            "error": error
        }
        try:
            with open("api_logs.json", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n---\n")
        except Exception as e:
            print(f"[LOG ERROR] Failed to write Gemini log: {e}")

    def _send_request(self, text: str, images: List[Dict] = None, model: str = None) -> ChatCompletionResponse:
        """Send request to Gemini"""
        url = f"{self.BASE_URL}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        params = {
            "bl": self.bl,
            "f.sid": "",
            "hl": "zh-CN",
            "_reqid": str(self.request_count * 100000 + random.randint(10000, 99999)),
            "rt": "c",
        }
        
        # Model ID mapping (select model via request header x-goog-ext-525001261-jspb)
        model_id = self.model_ids.get("flash", "56fdd199312815e2")  # Default flash version
        if model:
            model_lower = model.lower()
            if "pro" in model_lower:
                model_id = self.model_ids.get("pro", "e6fa609c3fa255c0")
            elif "thinking" in model_lower or "think" in model_lower:
                model_id = self.model_ids.get("thinking", "e051ce1aa80aa576")
        
        # Upload images and get paths
        image_paths = []
        if images and len(images) > 0:
            if not self.push_id:
                print("⚠️  Image upload requires push-id, please run: python get_push_id.py")
                print("   Then add the obtained push-id to config.py")
            else:
                try:
                    for img in images:
                        # Decode base64 data
                        img_data = base64.b64decode(img["data"])
                        # Upload and get path
                        path = self._upload_image(img_data, img["mime_type"])
                        image_paths.append(path)
                        if self.debug:
                            print(f"[DEBUG] Image uploaded successfully: {path[:50]}...")
                except Exception as e:
                    print(f"⚠️  Image upload failed: {e}")
                    image_paths = []
        
        req_data = self._build_request_data(text, images, image_paths, model)
        
        form_data = {
            "f.req": req_data,
            "at": self.snlm0e,
        }
        
        # Model selection request headers
        model_headers = {
            "x-goog-ext-525001261-jspb": json.dumps([1, None, None, None, model_id, None, None, 0, [4], None, None, 2], separators=(',', ':')),
        }
        
        # Build log entry
        gemini_request_log = {
            "url": url,
            "params": params,
            "text": text,
            "model": model,
            "model_id": model_id,
            "has_images": len(images) > 0 if images else False,
            "image_paths": image_paths,
            "f_req_preview": req_data[:500] + "..." if len(req_data) > 500 else req_data,
        }
        
        if self.debug:
            print(f"[DEBUG] Request URL: {url}")
            print(f"[DEBUG] AT Token: {self.snlm0e[:30]}...")
            print(f"[DEBUG] Model: {model or 'default'}, ID: {model_id}")
            if image_paths:
                print(f"[DEBUG] Request data first 300 characters: {req_data[:300]}")
        
        # Retry mechanism
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                resp = self.session.post(url, params=params, data=form_data, headers=model_headers, timeout=60.0)
            
                if self.debug:
                    print(f"[DEBUG] Response status: {resp.status_code}")
                    print(f"[DEBUG] Response content first 500 characters: {resp.text[:500]}")
                    # Always save full response for debugging
                    with open("debug_image_response.txt", "w", encoding="utf-8") as f:
                        f.write(resp.text)
                    print(f"[DEBUG] Full response saved to debug_image_response.txt")
                
                # Log full Gemini response
                self._log_gemini_call(gemini_request_log, resp.text)
                
                resp.raise_for_status()
                self.request_count += 1
                
                reply_text = self._parse_response(resp.text)
                
                # Save assistant reply
                self.messages.append(Message(role="assistant", content=reply_text))
                
                # Build OpenAI format response
                return ChatCompletionResponse(
                    id=f"chatcmpl-{self.conversation_id or 'gemini'}-{int(time.time())}",
                    created=int(time.time()),
                    model="gemini-web",
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=Message(role="assistant", content=reply_text),
                            finish_reason="stop"
                        )
                    ],
                    usage=Usage(
                        prompt_tokens=len(text),
                        completion_tokens=len(reply_text),
                        total_tokens=len(text) + len(reply_text)
                    )
                )
                
            except httpx.HTTPStatusError as e:
                self._log_gemini_call(gemini_request_log, e.response.text if hasattr(e, 'response') else "", error=f"HTTP {e.response.status_code}")
                raise Exception(f"HTTP error: {e.response.status_code}")
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
                # Network connection issues, retryable
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2, 4 seconds
                    print(f"⚠️  Connection interrupted, retrying after {wait_time} seconds ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                self._log_gemini_call(gemini_request_log, "", error=str(e))
                raise Exception(f"Network connection failed (retried {max_retries} times): {e}")
            except Exception as e:
                self._log_gemini_call(gemini_request_log, "", error=str(e))
                raise Exception(f"Request failed: {e}")
        
        # All retries failed
        if last_error:
            raise Exception(f"Request failed (retried {max_retries} times): {last_error}")
    
    def reset(self):
        """Reset session context"""
        self.conversation_id = ""
        self.response_id = ""
        self.choice_id = ""
        self.messages = []
    
    def get_history(self) -> List[Dict]:
        """Get message history (OpenAI format)"""
        return [{"role": m.role, "content": m.content} for m in self.messages]


# OpenAI compatible interface
class OpenAICompatible:
    """OpenAI SDK compatible wrapper"""
    
    def __init__(self, client: GeminiClient):
        self.client = client
        self.chat = self.Chat(client)
    
    class Chat:
        def __init__(self, client: GeminiClient):
            self.client = client
            self.completions = self.Completions(client)
        
        class Completions:
            def __init__(self, client: GeminiClient):
                self.client = client
            
            def create(
                self,
                model: str = "gemini-web",
                messages: List[Dict] = None,
                **kwargs
            ) -> ChatCompletionResponse:
                return self.client.chat(messages=messages)
