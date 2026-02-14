"""
Feishu Client - 飞书文档操作

功能:
- 创建/更新文档
- 上传图片
- 追加内容块
"""

import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from loguru import logger
import json
import os


class FeishuClient:
    """飞书API客户端"""
    
    def __init__(
        self,
        app_id: str = None,
        app_secret: str = None
    ):
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.base_url = "https://open.feishu.cn/open-apis"
        self.access_token = None
        self.token_expires_at = None
        
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        if self.access_token and self.token_expires_at:
            if datetime.now().timestamp() < self.token_expires_at - 60:
                return self.access_token
        
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        response = await self.client.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        })
        
        data = response.json()
        if data.get("code") != 0:
            raise Exception(f"Failed to get access token: {data}")
        
        self.access_token = data["tenant_access_token"]
        self.token_expires_at = datetime.now().timestamp() + data["expire"]
        
        return self.access_token
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> dict:
        """发送API请求"""
        token = await self._get_access_token()
        
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.base_url}{endpoint}"
        response = await self.client.request(method, url, headers=headers, **kwargs)
        
        return response.json()
    
    async def create_document(self, title: str, folder_token: str = None) -> dict:
        """创建新文档"""
        body = {
            "title": title,
            "folder_token": folder_token
        }
        
        result = await self._request("POST", "/docx/v1/documents", json=body)
        
        if result.get("code") != 0:
            raise Exception(f"Failed to create document: {result}")
        
        return result["data"]["document"]
    
    async def get_document(self, document_id: str) -> dict:
        """获取文档信息"""
        result = await self._request("GET", f"/docx/v1/documents/{document_id}")
        
        if result.get("code") != 0:
            raise Exception(f"Failed to get document: {result}")
        
        return result["data"]["document"]
    
    async def create_block(
        self,
        document_id: str,
        block_id: str,
        children: list[dict],
        index: int = -1
    ) -> dict:
        """在文档块下创建子块"""
        body = {
            "children": children,
            "index": index
        }
        
        result = await self._request(
            "POST",
            f"/docx/v1/documents/{document_id}/blocks/{block_id}/children",
            json=body
        )
        
        if result.get("code") != 0:
            raise Exception(f"Failed to create block: {result}")
        
        return result["data"]
    
    async def upload_media(
        self,
        file_path: str,
        parent_type: str = "docx_image",
        parent_node: str = None
    ) -> str:
        """上传媒体文件"""
        token = await self._get_access_token()
        
        with open(file_path, "rb") as f:
            files = {
                "file": (Path(file_path).name, f, "image/png")
            }
            data = {
                "file_type": "image",
                "parent_type": parent_type,
            }
            if parent_node:
                data["parent_node"] = parent_node
            
            response = await self.client.post(
                f"{self.base_url}/drive/v1/medias/upload_all",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data
            )
        
        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"Failed to upload media: {result}")
        
        return result["data"]["file_token"]
    
    def _build_text_block(self, text: str, style: dict = None) -> dict:
        """构建文本块"""
        block = {
            "block_type": 2,  # text
            "text": {
                "elements": [{
                    "text_run": {
                        "content": text
                    }
                }]
            }
        }
        if style:
            block["text"]["style"] = style
        return block
    
    def _build_heading_block(self, text: str, level: int = 1) -> dict:
        """构建标题块"""
        block_types = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11}
        return {
            "block_type": block_types.get(level, 3),
            f"heading{level}": {
                "elements": [{
                    "text_run": {
                        "content": text
                    }
                }]
            }
        }
    
    def _build_bullet_block(self, text: str) -> dict:
        """构建无序列表块"""
        return {
            "block_type": 12,  # bullet
            "bullet": {
                "elements": [{
                    "text_run": {
                        "content": text
                    }
                }]
            }
        }
    
    def _build_divider_block(self) -> dict:
        """构建分隔线块"""
        return {
            "block_type": 22,  # divider
            "divider": {}
        }
    
    def _build_image_block(self, file_token: str) -> dict:
        """构建图片块"""
        return {
            "block_type": 27,  # image
            "image": {
                "token": file_token
            }
        }
    
    def _build_callout_block(self, text: str, emoji: str = "📰") -> dict:
        """构建高亮块"""
        return {
            "block_type": 19,  # callout
            "callout": {
                "emoji_id": emoji,
                "elements": [{
                    "text_run": {
                        "content": text
                    }
                }]
            }
        }
    
    async def append_daily_briefing(
        self,
        document_id: str,
        briefing_content: dict
    ):
        """追加每日简报内容到文档"""
        
        # 获取文档根块ID
        doc = await self.get_document(document_id)
        root_block_id = document_id  # 通常文档ID就是根块ID
        
        blocks = []
        
        # 日期标题
        blocks.append(self._build_divider_block())
        blocks.append(self._build_heading_block(
            f"📅 {briefing_content['date']}", level=2
        ))
        blocks.append(self._build_divider_block())
        
        # 今日概览
        blocks.append(self._build_heading_block("📊 今日概览", level=3))
        blocks.append(self._build_callout_block(briefing_content.get('summary', '')))
        
        # 各分类新闻
        for category_data in briefing_content.get('categories', []):
            blocks.append(self._build_heading_block(
                f"{category_data['icon']} {category_data['name']}", level=3
            ))
            
            for article in category_data.get('articles', []):
                # 文章标题（双语）
                blocks.append(self._build_heading_block(article['title_original'], level=4))
                blocks.append(self._build_heading_block(article['title_zh'], level=4))
                
                # 元信息
                blocks.append(self._build_text_block(
                    f"来源: {article['source']} | 时间: {article['published_at']}"
                ))
                
                # 摘要
                blocks.append(self._build_text_block(article['summary_zh']))
                
                # 要点
                for point in article.get('key_points', []):
                    blocks.append(self._build_bullet_block(point))
                
                # 链接
                blocks.append(self._build_text_block(f"🔗 原文: {article['url']}"))
                
                blocks.append(self._build_divider_block())
        
        # 预测部分
        blocks.append(self._build_heading_block("🎯 未来预测", level=3))
        for prediction in briefing_content.get('predictions', []):
            blocks.append(self._build_text_block(
                f"【{prediction['timeframe']}】{prediction['content']}"
            ))
        
        # 批量创建块
        await self.create_block(document_id, root_block_id, blocks)
        
        logger.info(f"Appended {len(blocks)} blocks to document {document_id}")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


async def main():
    """测试飞书客户端"""
    client = FeishuClient()
    
    # 测试创建文档
    # doc = await client.create_document("测试简报")
    # print(f"Created document: {doc}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
