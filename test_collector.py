#!/usr/bin/env python3
"""
快速测试新闻采集功能
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from collector import NewsCollector


async def test():
    """测试采集"""
    print("🚀 Starting news collection test...")
    print("=" * 60)
    
    collector = NewsCollector(config_path="config/sources.yaml")
    print(f"📰 Loaded {len(collector.sources)} news sources")
    
    # RSS源统计
    rss_sources = [s for s in collector.sources if s.source_type == 'rss' and s.rss_url]
    web_sources = [s for s in collector.sources if s.source_type == 'web']
    print(f"   - RSS sources: {len(rss_sources)}")
    print(f"   - Web sources: {len(web_sources)}")
    print()
    
    # 采集最近24小时的新闻
    since = datetime.now() - timedelta(hours=24)
    print(f"⏰ Fetching articles since: {since}")
    print()
    
    articles = await collector.collect_all(since)
    await collector.close()
    
    print()
    print("=" * 60)
    print(f"✅ Total articles collected: {len(articles)}")
    print()
    
    # 按来源统计
    sources_count = {}
    for article in articles:
        sources_count[article.source] = sources_count.get(article.source, 0) + 1
    
    print("📊 Articles by source:")
    for source, count in sorted(sources_count.items(), key=lambda x: -x[1]):
        print(f"   - {source}: {count}")
    print()
    
    # 显示前10篇文章
    print("📝 Sample articles (first 10):")
    print("-" * 60)
    for i, article in enumerate(articles[:10], 1):
        print(f"{i}. [{article.source}] {article.title[:60]}...")
        print(f"   URL: {article.url}")
        print(f"   Time: {article.published_at}")
        print(f"   Content: {len(article.content or '')} chars")
        print()
    
    return articles


if __name__ == "__main__":
    articles = asyncio.run(test())
