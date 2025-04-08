from dataclasses import dataclass
from typing import List, Optional, Dict, Any, ClassVar
from pathlib import Path
import json
from playwright.sync_api import Request, Response

DEFAULT_INCLUDE_MIME = ["html", "script", "xml", "flash", "other_text"]
DEFAULT_INCLUDE_STATUS = ["2xx", "3xx", "4xx", "5xx"]
MAX_PAYLOAD_SIZE = 4000

@dataclass
class HTTPRequestData:
    """Internal representation of HTTP request data"""
    method: str
    url: str
    headers: Dict[str, str]
    post_data: Optional[str]
    redirected_from_url: Optional[str]
    redirected_to_url: Optional[str] 
    is_iframe: bool

class HTTPRequest:
    """HTTP request class with unified implementation"""
    def __init__(self, data: HTTPRequestData):
        self._data = data

    @property
    def method(self) -> str:
        return self._data.method

    @property
    def url(self) -> str:
        return self._data.url

    @property
    def headers(self) -> Dict[str, str]:
        return self._data.headers

    @property
    def post_data(self) -> Optional[str]:
        return self._data.post_data

    @property
    def redirected_from(self) -> Optional["HTTPRequest"]:
        if self._data.redirected_from_url:
            # Create minimal request object for redirect
            data = HTTPRequestData(
                method="",
                url=self._data.redirected_from_url,
                headers={},
                post_data=None,
                redirected_from_url=None,
                redirected_to_url=None,
                is_iframe=False
            )
            return HTTPRequest(data)
        return None

    @property
    def redirected_to(self) -> Optional["HTTPRequest"]:
        if self._data.redirected_to_url:
            # Create minimal request object for redirect
            data = HTTPRequestData(
                method="",
                url=self._data.redirected_to_url,
                headers={},
                post_data=None,
                redirected_from_url=None,
                redirected_to_url=None,
                is_iframe=False
            )
            return HTTPRequest(data)
        return None

    @property
    def is_iframe(self) -> bool:
        return self._data.is_iframe

    async def to_json(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "post_data": self.post_data,
            "redirected_from": self._data.redirected_from_url,
            "redirected_to": self._data.redirected_to_url,
            "is_iframe": self.is_iframe
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "HTTPRequest":
        request_data = HTTPRequestData(
            method=data["method"],
            url=data["url"],
            headers=data["headers"],
            post_data=data["post_data"],
            redirected_from_url=data["redirected_from"],
            redirected_to_url=data["redirected_to"],
            is_iframe=data["is_iframe"]
        )
        return cls(request_data)

    @classmethod
    def from_pw(cls, request: Request) -> "HTTPRequest":
        request_data = HTTPRequestData(
            method=request.method,
            url=request.url,
            headers=dict(request.headers),
            post_data=request.post_data,
            redirected_from_url=request.redirected_from.url if request.redirected_from else None,
            redirected_to_url=request.redirected_to.url if request.redirected_to else None,
            is_iframe=bool(request.frame.parent_frame)
        )
        return cls(request_data)

    def __str__(self) -> str:
        """String representation of HTTP request"""
        req_str = "[Request]: " + str(self.method) + " " + str(self.url) + "\n"
        
        if self.redirected_from:
            req_str += "Redirected from: " + str(self.redirected_from.url) + "\n"
        if self.redirected_to:
            req_str += "Redirecting to: " + str(self.redirected_to.url) + "\n"
        if self.is_iframe:
            req_str += "From iframe\n"

        req_str += str(self.headers) + "\n"
        req_str += str(self.post_data)
        return req_str

@dataclass
class HTTPResponseData:
    """Internal representation of HTTP response data"""
    url: str
    status: int
    headers: Dict[str, str]
    is_iframe: bool
    body: Optional[bytes] = None
    body_error: Optional[str] = None

class HTTPResponse:
    """HTTP response class with unified implementation"""
    def __init__(self, data: HTTPResponseData):
        self._data = data

    @property
    def url(self) -> str:
        return self._data.url

    @property
    def status(self) -> int:
        return self._data.status

    @property
    def headers(self) -> Dict[str, str]:
        return self._data.headers

    @property
    def is_iframe(self) -> bool:
        return self._data.is_iframe

    async def get_body(self) -> bytes:
        if self._data.body_error:
            raise Exception(self._data.body_error)
        if self._data.body is None:
            raise Exception("Response body not available")
        return self._data.body

    def get_content_type(self) -> str:
        """Get content type from response headers"""
        if not self.headers:
            return ""
        content_type = self.headers.get("content-type", "")
        return content_type.lower()
    
    def get_status_code(self) -> int:
        """Get HTTP status code"""
        if not self.status:
            return 0
        return self.status
    
    def get_response_size(self) -> int:
        """Get response payload size in bytes"""
        if not self.headers:
            return 0
        content_length = self.headers.get("content-length")
        if content_length and content_length.isdigit():
            return int(content_length)
        return 0

    async def to_json(self) -> Dict[str, Any]:
        json_data = {
            "url": self.url,
            "status": self.status,
            "headers": self.headers,
            "content_type": self.get_content_type(),
            "content_length": self.get_response_size(),
            "is_iframe": self.is_iframe
        }

        if not (300 <= self.status < 400):
            if self._data.body_error:
                json_data["body_error"] = self._data.body_error
            elif self._data.body:
                json_data["body"] = str(self._data.body)

        return json_data

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "HTTPResponse":
        response_data = HTTPResponseData(
            url=data["url"],
            status=data["status"],
            headers=data["headers"],
            is_iframe=data["is_iframe"],
            body=data.get("body", "").encode() if "body" in data else None,
            body_error=data.get("body_error")
        )
        return cls(response_data)

    @classmethod
    def from_pw(cls, response: Response) -> "HTTPResponse":
        response_data = HTTPResponseData(
            url=response.url,
            status=response.status,
            headers=dict(response.headers),
            is_iframe=bool(response.frame.parent_frame)
        )
        return cls(response_data)

    async def to_str(self) -> str:
        """String representation of HTTP response"""
        resp_str = "[Response]: " + str(self.url) + " " + str(self.status) + "\n"
        
        if self.is_iframe:
            resp_str += "From iframe\n"
        resp_str += str(self.headers) + "\n"
        
        if 300 <= self.status < 400:
            resp_str += "[Redirect response - no body]"
            return resp_str
            
        try:
            resp_bytes = await self.get_body()
            resp_str += str(resp_bytes)
        except Exception as e:
            resp_str += f"[Error getting response body: {str(e)}]"
            
        return resp_str

@dataclass
class HTTPMessage:
    """Encapsulates a request/response pair"""
    request: HTTPRequest 
    response: Optional[HTTPResponse]

    async def to_str(self) -> str:
        req_str = str(self.request)
        resp_str = await self.response.to_str() if self.response else ""
        return f"{req_str}\n{resp_str}"

    async def to_json(self) -> Dict[str, Any]:
        json_data = {
            "request": await self.request.to_json()
        }
        if self.response:
            json_data["response"] = await self.response.to_json()
        return json_data

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "HTTPMessage":
        request = HTTPRequest.from_json(data["request"])
        response = HTTPResponse.from_json(data["response"]) if data.get("response") else None
        return cls(request=request, response=response)

@dataclass
class HTTPMessageSession:
    """A collection of HTTP messages with a name"""
    messages: List[HTTPMessage]
    name: str

    async def to_json(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "messages": [await msg.to_json() for msg in self.messages]
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "HTTPMessageSession":
        messages = [HTTPMessage.from_json(msg_data) for msg_data in data["messages"]]
        return cls(messages=messages, name=data["name"])

    async def to_json_file(self, json_path: Path) -> None:
        json_data = await self.to_json()
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2)

    @classmethod
    async def from_json_file(cls, json_path: Path) -> "HTTPMessageSession":
        with open(json_path, "r") as f:
            data = json.load(f)
        return cls.from_json(data)