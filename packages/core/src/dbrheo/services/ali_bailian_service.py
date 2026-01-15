"""
阿里百炼API服务 - 处理与阿里云百炼平台API的通信
支持通义千问等模型，保持与其他服务相同的接口
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Iterator
import requests
from ..types.core_types import Content, Part, AbortSignal
from ..config.base import DatabaseConfig
from ..utils.debug_logger import DebugLogger, log_info, log_error
from ..utils.retry_with_backoff import retry_decorator, RetryOptions


class AliBailianService:
    """
    阿里百炼API服务
    - 与阿里云百炼API的通信
    - 消息格式转换
    - 流式响应处理
    - 错误处理和重试
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._setup_api()
        # 用于累积流式工具调用
        self._tool_call_buffer = {}
        
    def _setup_api(self):
        """设置阿里百炼API"""
        # 获取API密钥（支持DASHSCOPE_API_KEY和ALI_BAILIAN_API_KEY）
        api_key = (
            self.config.get("ali_bailian_api_key") or
            self.config.get("dashscope_api_key") or
            os.getenv("DASHSCOPE_API_KEY") or
            os.getenv("ALI_BAILIAN_API_KEY")
        )
        
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY or ALI_BAILIAN_API_KEY environment variable is required")
            
        # 获取应用ID（可选，使用兼容模式时不需要）
        app_id = (
            self.config.get("ali_bailian_app_id") or
            os.getenv("ALI_BAILIAN_APP_ID") or
            "default"  # 默认值，兼容模式不需要
        )
            
        # 获取API端点（支持DASHSCOPE_BASE_URL）
        api_base = (
            self.config.get("dashscope_base_url") or
            self.config.get("ali_bailian_api_base") or
            os.getenv("DASHSCOPE_BASE_URL") or
            os.getenv("ALI_BAILIAN_API_BASE") or
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        self.api_key = api_key
        self.app_id = app_id
        self.api_base = api_base
        
        # 模型映射
        model_name = self.config.get_model() or "qwen-turbo"
        
        # 映射简短名称到完整模型名
        model_mappings = {
            "qwen": "qwen-turbo",
            "qwen-turbo": "qwen-turbo",
            "qwen-plus": "qwen-plus",
            "qwen-max": "qwen-max",
            "qwen-vl": "qwen-vl-plus",
            "ali": "qwen-turbo",
            "ali-bailian": "qwen-turbo",
        }
        
        # 处理模型名称
        if model_name in model_mappings:
            self.model_name = model_mappings[model_name]
        else:
            # 如果未知模型，尝试直接使用
            self.model_name = model_name
            
        # 设置请求头
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        log_info("AliBailianService", f"Initialized with model: {self.model_name}")
        
    def _convert_messages_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将Gemini格式消息转换为阿里百炼格式
        """
        bailian_messages = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            # 转换角色名称
            if role == "model":
                role = "assistant"
            elif role == "user":
                role = "user"
            else:
                # 其他角色统一为user
                role = "user"
                
            bailian_messages.append({
                "role": role,
                "content": content
            })
            
        return bailian_messages
        
    def _prepare_request_data(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """准备请求数据"""
        # 转换消息格式
        formatted_messages = self._convert_messages_format(messages)
        
        # 构建请求数据
        data = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": kwargs.get("stream", False)
        }
        
        # 添加其他可选参数
        if "temperature" in kwargs:
            data["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            data["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            data["top_p"] = kwargs["top_p"]
            
        return data
        
    @retry_decorator(max_attempts=3)
    def generate_response(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        生成响应（非流式）
        
        Args:
            messages: 消息历史
            **kwargs: 其他参数
            
        Returns:
            生成的文本响应
        """
        data = self._prepare_request_data(messages, **kwargs)
        data["stream"] = False
        
        try:
            # 使用OpenAI兼容模式端点
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                log_error("AliBailianService", error_msg)
                raise Exception(error_msg)
                
            result = response.json()
            
            # 提取响应文本
            if "output" in result and "text" in result["output"]:
                return result["output"]["text"]
            elif "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
            else:
                error_msg = f"Unexpected response format: {result}"
                log_error("AliBailianService", error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            log_error("AliBailianService", f"Error generating response: {e}")
            raise
            
    def generate_streaming_response(self, messages: List[Dict[str, Any]], **kwargs) -> Iterator[str]:
        """
        生成流式响应
        
        Args:
            messages: 消息历史
            **kwargs: 其他参数
            
        Returns:
            文本块迭代器
        """
        data = self._prepare_request_data(messages, **kwargs)
        data["stream"] = True
        
        try:
            # 使用OpenAI兼容模式端点
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=data,
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                log_error("AliBailianService", error_msg)
                raise Exception(error_msg)
                
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        
                        if data_str == "[DONE]":
                            break
                            
                        try:
                            data_obj = json.loads(data_str)
                            
                            # 提取文本块
                            if "output" in data_obj and "text" in data_obj["output"]:
                                yield data_obj["output"]["text"]
                            elif "choices" in data_obj and len(data_obj["choices"]) > 0:
                                yield data_obj["choices"][0]["delta"]["content"]
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            log_error("AliBailianService", f"Error in streaming response: {e}")
            raise
            
    def generate_response_with_functions(self, messages: List[Dict[str, Any]], functions: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """
        生成带函数调用的响应
        
        Args:
            messages: 消息历史
            functions: 可用函数列表
            **kwargs: 其他参数
            
        Returns:
            包含响应或函数调用的字典
        """
        # 转换函数格式为阿里百炼格式
        bailian_functions = []
        for function in functions:
            bailian_function = {
                "name": function.get("name"),
                "description": function.get("description", ""),
                "parameters": function.get("parameters", {})
            }
            bailian_functions.append(bailian_function)
        
        data = self._prepare_request_data(messages, **kwargs)
        data["functions"] = bailian_functions
        data["stream"] = False
        
        try:
            # 使用OpenAI兼容模式端点
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                log_error("AliBailianService", error_msg)
                raise Exception(error_msg)
                
            result = response.json()
            
            # 检查是否有函数调用
            if "output" in result and "text" in result["output"]:
                return {"content": result["output"]["text"]}
            elif "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                if "function_call" in choice["message"]:
                    return {
                        "function_call": {
                            "name": choice["message"]["function_call"]["name"],
                            "arguments": choice["message"]["function_call"]["arguments"]
                        }
                    }
                else:
                    return {"content": choice["message"]["content"]}
            else:
                error_msg = f"Unexpected response format: {result}"
                log_error("AliBailianService", error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            log_error("AliBailianService", f"Error generating response with functions: {e}")
            raise
            
    def count_tokens(self, text: str) -> int:
        """
        估算文本的token数量
        
        Args:
            text: 要计算的文本
            
        Returns:
            估算的token数量
        """
        # 简单的token估算：中文字符按1个token计算，英文单词按0.75个token计算
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return chinese_chars + int(english_chars * 0.75)
        
    def send_message_stream(
        self, 
        contents: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        signal: Optional[AbortSignal] = None,
        temperature: Optional[float] = None, 
        max_tokens: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        发送消息并返回流式响应（对齐Gemini接口）
        支持工具调用（function calling）
        """
        # 重置工具调用缓冲区
        self._tool_call_buffer = {}
        
        # 转换消息格式
        messages = self._convert_to_openai_format(contents, system_instruction)
        
        # 构建请求数据
        data = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }
        
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
            
        # 添加工具（如果有）
        if tools:
            data["tools"] = self._convert_tools_format(tools)
            
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self.headers,
                json=data,
                stream=True,
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"API error {response.status_code}: {response.text}"
                log_error("AliBailianService", error_msg)
                yield {"text": f"Error: {error_msg}"}
                return
                
            for line in response.iter_lines():
                if signal and signal.aborted:
                    break
                    
                if line:
                    line = line.decode('utf-8')
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        if data_str == "[DONE]":
                            # 流结束，返回累积的工具调用
                            if self._tool_call_buffer:
                                function_calls = []
                                for tc_id, tc_data in self._tool_call_buffer.items():
                                    if tc_data.get("name") and tc_data.get("arguments"):
                                        try:
                                            args = json.loads(tc_data["arguments"])
                                            function_calls.append({
                                                "id": tc_id,
                                                "name": tc_data["name"],
                                                "args": args
                                            })
                                        except:
                                            pass
                                if function_calls:
                                    yield {"function_calls": function_calls}
                            break
                            
                        try:
                            chunk = json.loads(data_str)
                            processed = self._process_chunk(chunk)
                            if processed:
                                yield processed
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            log_error("AliBailianService", f"Stream error: {e}")
            yield {"text": f"Error: {str(e)}"}
    
    def _convert_to_openai_format(self, contents: List[Dict[str, Any]], system_instruction: Optional[str]) -> List[Dict[str, Any]]:
        """转换为 OpenAI 兼容格式"""
        messages = []
        
        # 添加系统指令
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        
        # 转换历史消息
        for content in contents:
            role = content.get("role", "user")
            if role == "model":
                role = "assistant"
                
            parts = content.get("parts", [])
            
            # 处理文本内容
            text_parts = []
            for part in parts:
                if isinstance(part, dict):
                    if "text" in part:
                        text_parts.append(part["text"])
                    elif "function_call" in part:
                        # 函数调用
                        fc = part["function_call"]
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": fc.get("id", "call_0"),
                                "type": "function",
                                "function": {
                                    "name": fc["name"],
                                    "arguments": json.dumps(fc["args"])
                                }
                            }]
                        })
                        continue
                    elif "function_response" in part or "functionResponse" in part:
                        # 函数响应
                        fr = part.get("function_response") or part.get("functionResponse")
                        messages.append({
                            "role": "tool",
                            "tool_call_id": fr.get("id", "call_0"),
                            "content": json.dumps(fr.get("response", {}))
                        })
                        continue
                        
            if text_parts:
                messages.append({"role": role, "content": "\n".join(text_parts)})
                
        return messages
    
    def _convert_tools_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换工具格式为 OpenAI 兼容格式"""
        converted = []
        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            })
        return converted
    
    def _process_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理流式响应块，累积工具调用"""
        if "choices" not in chunk or not chunk["choices"]:
            return None
            
        choice = chunk["choices"][0]
        delta = choice.get("delta", {})
        
        result = {}
        
        # 文本内容 - 直接返回
        if "content" in delta and delta["content"]:
            result["text"] = delta["content"]
            
        # 工具调用 - 累积到缓冲区，不立即返回
        if "tool_calls" in delta and delta["tool_calls"]:
            for tc in delta["tool_calls"]:
                tc_id = tc.get("id", "call_0")
                tc_index = tc.get("index", 0)
                
                # 初始化缓冲区
                if tc_id not in self._tool_call_buffer:
                    self._tool_call_buffer[tc_id] = {"name": "", "arguments": ""}
                
                # 累积函数名称
                if tc.get("function") and tc["function"].get("name"):
                    self._tool_call_buffer[tc_id]["name"] = tc["function"]["name"]
                
                # 累积参数（可能分多个块）
                if tc.get("function") and tc["function"].get("arguments"):
                    self._tool_call_buffer[tc_id]["arguments"] += tc["function"]["arguments"]
                
        return result if result else None
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取当前模型信息
        
        Returns:
            包含模型信息的字典
        """
        return {
            "name": self.model_name,
            "provider": "ali_bailian",
            "app_id": self.app_id,
            "api_base": self.api_base
        }
