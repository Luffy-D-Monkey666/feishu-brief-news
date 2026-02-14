"""
LLM Client - 统一的 LLM 调用接口

支持:
- DeepSeek (推荐，性价比高)
- OpenAI
- Anthropic
"""

import os
from typing import Optional
from loguru import logger


class LLMClient:
    """统一 LLM 客户端"""
    
    def __init__(self, provider: str = None):
        """
        初始化 LLM 客户端
        
        provider: deepseek / openai / anthropic
        如果不指定，按优先级自动检测
        """
        self.provider = provider or self._detect_provider()
        self._init_client()
        logger.info(f"LLM Client initialized with provider: {self.provider}")
    
    def _detect_provider(self) -> str:
        """自动检测可用的 provider"""
        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        raise ValueError("No LLM API key found. Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY")
    
    def _init_client(self):
        """初始化对应的客户端"""
        if self.provider == "deepseek":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            self.model = "deepseek-chat"  # DeepSeek V3
            
        elif self.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI()
            self.model = "gpt-4-turbo-preview"
            
        elif self.provider == "anthropic":
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic()
            self.model = "claude-3-5-sonnet-20241022"
            
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def chat(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """
        发送聊天请求
        
        Args:
            prompt: 用户提示
            system: 系统提示
            max_tokens: 最大输出 token
            temperature: 温度参数
        
        Returns:
            LLM 响应文本
        """
        try:
            if self.provider == "anthropic":
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                return response.content[0].text
            else:
                # OpenAI / DeepSeek 格式
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""
    
    async def close(self):
        """关闭客户端（如果需要）"""
        pass


# 全局单例
_client: Optional[LLMClient] = None


def get_llm_client(provider: str = None) -> LLMClient:
    """获取 LLM 客户端（单例）"""
    global _client
    if _client is None:
        _client = LLMClient(provider)
    return _client


async def chat(prompt: str, system: str = "", **kwargs) -> str:
    """便捷函数：直接调用 LLM"""
    client = get_llm_client()
    return await client.chat(prompt, system, **kwargs)
