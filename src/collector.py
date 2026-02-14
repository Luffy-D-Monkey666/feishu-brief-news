"""
News Collector - 新闻采集模块

支持多种采集方式:
- RSS Feed
- Web Scraping (Playwright)
- Jina Reader API
- Trafilatura
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import feedparser
import httpx
from loguru import logger
import yaml
from pathlib import Path
import trafilatura

from models import RawArticle, NewsSource


class NewsCollector:
    """新闻采集器"""
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        self.config_path = Path(config_path)
        self.sources = self._load_sources()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
        
    def _load_sources(self) -> list[NewsSource]:
        """加载新闻源配置"""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        sources = []
        for region, categories in config.items():
            if isinstance(categories, list):
                # 直接是列表（如 japan, korea）
                for item in categories:
                    sources.append(NewsSource(
                        name=item['name'],
                        url=item['url'],
                        source_type=item.get('type', 'web'),
                        language=item.get('lang', 'en'),
                        rss_url=item.get('rss'),
                        region=region
                    ))
            else:
                # 嵌套的分类结构（如 china, us）
                for category, items in categories.items():
                    for item in items:
                        sources.append(NewsSource(
                            name=item['name'],
                            url=item['url'],
                            source_type=item.get('type', 'web'),
                            language=item.get('lang', 'en'),
                            rss_url=item.get('rss'),
                            region=region
                        ))
        
        logger.info(f"Loaded {len(sources)} news sources")
        return sources
    
    def _generate_article_id(self, url: str) -> str:
        """生成文章唯一ID"""
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    async def fetch_rss(self, source: NewsSource, since: datetime) -> list[RawArticle]:
        """从RSS源获取文章"""
        if not source.rss_url:
            return []
            
        try:
            response = await self.client.get(source.rss_url)
            feed = feedparser.parse(response.text)
            
            articles = []
            for entry in feed.entries:
                # 解析发布时间
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()
                
                # 只获取指定时间之后的文章
                if published < since:
                    continue
                
                # 提取图片
                images = []
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if media.get('type', '').startswith('image'):
                            images.append(media['url'])
                if hasattr(entry, 'enclosures'):
                    for enc in entry.enclosures:
                        if enc.get('type', '').startswith('image'):
                            images.append(enc['href'])
                
                article = RawArticle(
                    id=self._generate_article_id(entry.link),
                    title=entry.title,
                    url=entry.link,
                    source=source.name,
                    source_url=source.url,
                    published_at=published,
                    content=entry.get('summary', ''),
                    author=entry.get('author'),
                    image_urls=images,
                    language=source.language
                )
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} articles from {source.name} (RSS)")
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch RSS from {source.name}: {e}")
            return []
    
    async def fetch_web_jina(self, url: str) -> Optional[str]:
        """使用Jina Reader API提取网页内容"""
        try:
            jina_url = f"https://r.jina.ai/{url}"
            response = await self.client.get(jina_url)
            return response.text
        except Exception as e:
            logger.error(f"Jina fetch failed for {url}: {e}")
            return None
    
    async def fetch_web_trafilatura(self, url: str) -> Optional[str]:
        """使用trafilatura提取网页内容"""
        try:
            response = await self.client.get(url)
            content = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=True,
                include_images=True
            )
            return content
        except Exception as e:
            logger.error(f"Trafilatura fetch failed for {url}: {e}")
            return None
    
    async def fetch_web_source(self, source: NewsSource, since: datetime) -> list[RawArticle]:
        """从网页源获取文章列表"""
        # 这里需要针对不同网站实现不同的爬取逻辑
        # 简化版：使用通用方法
        try:
            content = await self.fetch_web_jina(source.url)
            if not content:
                content = await self.fetch_web_trafilatura(source.url)
            
            if content:
                # TODO: 解析内容提取文章列表
                # 这里需要更复杂的逻辑来识别文章链接
                logger.info(f"Fetched content from {source.name} (Web)")
                pass
                
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch web from {source.name}: {e}")
            return []
    
    async def fetch_article_content(self, article: RawArticle) -> RawArticle:
        """获取文章完整内容"""
        if article.content and len(article.content) > 500:
            return article
        
        # 尝试获取完整内容
        content = await self.fetch_web_jina(article.url)
        if not content:
            content = await self.fetch_web_trafilatura(article.url)
        
        if content:
            article.content = content
            
        return article
    
    async def collect_all(self, since: datetime) -> list[RawArticle]:
        """从所有源采集新闻"""
        all_articles = []
        
        # RSS源并行采集
        rss_sources = [s for s in self.sources if s.source_type == 'rss' and s.rss_url]
        rss_tasks = [self.fetch_rss(source, since) for source in rss_sources]
        rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
        
        for result in rss_results:
            if isinstance(result, list):
                all_articles.extend(result)
        
        # Web源（暂时跳过，需要更多定制化开发）
        # web_sources = [s for s in self.sources if s.source_type == 'web']
        
        logger.info(f"Total collected: {len(all_articles)} articles")
        
        # 获取完整内容（限制并发）
        semaphore = asyncio.Semaphore(10)
        
        async def fetch_with_semaphore(article):
            async with semaphore:
                return await self.fetch_article_content(article)
        
        content_tasks = [fetch_with_semaphore(a) for a in all_articles]
        all_articles = await asyncio.gather(*content_tasks, return_exceptions=True)
        all_articles = [a for a in all_articles if isinstance(a, RawArticle)]
        
        return all_articles
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


async def main():
    """测试采集"""
    collector = NewsCollector()
    since = datetime.now() - timedelta(days=1)
    articles = await collector.collect_all(since)
    
    for article in articles[:10]:
        print(f"- [{article.source}] {article.title}")
        print(f"  URL: {article.url}")
        print(f"  Published: {article.published_at}")
        print()
    
    await collector.close()


if __name__ == "__main__":
    asyncio.run(main())
