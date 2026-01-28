"""
Gemini OpenAI compatible API

Provides an interface fully compatible with the OpenAI SDK, allowing direct replacement of the OpenAI library.

Usage:
    from api import GeminiOpenAI
    
    client = GeminiOpenAI()
    response = client.chat.completions.create(
        model="gemini",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print(response.choices[0].message.content)
"""

from client import GeminiClient, ChatCompletionResponse, Message, ChatCompletionChoice, Usage
from config import SECURE_1PSID, SNLM0E, COOKIES_STR, PUSH_ID
from typing import List, Dict, Any, Optional, Union
import base64
import time


class GeminiOpenAI:
    """
    OpenAI SDK compatible Gemini client
    
    Usage is exactly the same as openai.OpenAI()
    """
    
    def __init__(
        self,
        cookies_str: str = None,
        snlm0e: str = None,
        push_id: str = None,
        secure_1psid: str = None,
    ):
        """
        Initialize the client
        
        Args:
            cookies_str: Full cookie string (recommended, required for image functionality)
            snlm0e: AT Token (required)
            push_id: Image upload ID (required for image functionality)
            secure_1psid: __Secure-1PSID cookie (if not using cookies_str)
        """
        self._client = GeminiClient(
            secure_1psid=secure_1psid or SECURE_1PSID,
            snlm0e=snlm0e or SNLM0E,
            cookies_str=cookies_str or COOKIES_STR,
            push_id=push_id or PUSH_ID,
            debug=False,
        )
        self.chat = self._Chat(self._client)
    
    class _Chat:
        def __init__(self, client: GeminiClient):
            self._client = client
            self.completions = self._Completions(client)
        
        class _Completions:
            def __init__(self, client: GeminiClient):
                self._client = client
            
            def create(
                self,
                model: str = "gemini",
                messages: List[Dict[str, Any]] = None,
                stream: bool = False,
                **kwargs
            ) -> ChatCompletionResponse:
                """
                Create a chat completion
                
                Args:
                    model: Model name (ignored, always uses Gemini)
                    messages: List of messages in OpenAI format
                    stream: Whether to stream output (not supported yet)
                    **kwargs: Other parameters (ignored)
                
                Returns:
                    ChatCompletionResponse: OpenAI format response
                
                Example:
                    # 纯文本
                    response = client.chat.completions.create(
                        model="gemini",
                        messages=[{"role": "user", "content": "Hello"}]
                    )
                    
                    # With image
                    response = client.chat.completions.create(
                        model="gemini",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What is this?"},
                                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                            ]
                        }]
                    )
                """
                if stream:
                    raise NotImplementedError("Streaming output is not supported yet")
                
                return self._client.chat(messages=messages)
    
    def reset(self):
        """Reset the conversation context"""
        self._client.reset()
    
    def get_history(self) -> List[Dict]:
        """Get message history"""
        return self._client.get_history()


# Convenience functions
def create_client(
    cookies_str: str = None,
    snlm0e: str = None,
    push_id: str = None,
) -> GeminiOpenAI:
    """
    Create a Gemini client (OpenAI compatible)
    
    Args:
        cookies_str: Full cookie string
        snlm0e: AT Token
        push_id: Image upload ID
    
    Returns:
        GeminiOpenAI: OpenAI compatible client
    """
    return GeminiOpenAI(
        cookies_str=cookies_str,
        snlm0e=snlm0e,
        push_id=push_id,
    )


def chat(
    message: str,
    image: bytes = None,
    image_path: str = None,
    reset: bool = False,
) -> str:
    """
    Quick chat function (singleton pattern)
    
    Args:
        message: Message text
        image: Image binary data
        image_path: Image file path
        reset: Whether to reset the context
    
    Returns:
        str: AI reply text
    
    Example:
        from api import chat
        
        # Plain text
        reply = chat("Hello")
        
        # With image
        reply = chat("What is this?", image_path="photo.jpg")
        
        # Reset context
        reply = chat("New topic", reset=True)
    """
    global _default_client
    
    if '_default_client' not in globals() or _default_client is None:
        _default_client = GeminiOpenAI()
    
    if reset:
        _default_client.reset()
    
    # Handle image
    img_data = None
    if image:
        img_data = image
    elif image_path:
        with open(image_path, 'rb') as f:
            img_data = f.read()
    
    # Build messages
    if img_data:
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": message},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(img_data).decode()}"}
                }
            ]
        }]
    else:
        messages = [{"role": "user", "content": message}]
    
    response = _default_client.chat.completions.create(messages=messages)
    return response.choices[0].message.content


_default_client: GeminiOpenAI = None
