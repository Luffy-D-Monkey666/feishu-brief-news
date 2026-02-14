#!/usr/bin/env python3
"""
每日简报生成脚本 - 用于定时任务调用
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent / "src"))

from models import Category, DailyBriefing
from collector import NewsCollector
from processor import NewsProcessor
from predictor import Predictor
from generator import MarkdownGenerator
from loguru import logger


async def run_daily_briefing():
    """执行每日简报生成"""
    
    # 目标日期：昨天
    target_date = datetime.now() - timedelta(days=1)
    
    logger.info(f"===== Daily Briefing for {target_date.strftime('%Y-%m-%d')} =====")
    
    # 时间范围
    since = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    until = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Step 1: 采集
    logger.info("Step 1: Collecting news...")
    collector = NewsCollector(config_path=str(Path(__file__).parent / "config/sources.yaml"))
    raw_articles = await collector.collect_all(since)
    await collector.close()
    
    # 过滤时间范围
    raw_articles = [a for a in raw_articles if since <= a.published_at <= until]
    logger.info(f"Collected {len(raw_articles)} articles")
    
    if not raw_articles:
        logger.warning("No articles found!")
        return None
    
    # Step 2: 处理
    logger.info("Step 2: Processing articles...")
    processor = NewsProcessor(
        categories_config=str(Path(__file__).parent / "config/categories.yaml"),
        people_config=str(Path(__file__).parent / "config/key_people.yaml")
    )
    processed_articles = await processor.process_all(raw_articles)
    logger.info(f"Processed {len(processed_articles)} articles")
    
    # 按分类整理
    articles_by_category = {category: [] for category in Category}
    for article in processed_articles:
        articles_by_category[article.category].append(article)
    
    for category in articles_by_category:
        articles_by_category[category].sort(key=lambda x: x.published_at, reverse=True)
    
    # Step 3: 预测
    logger.info("Step 3: Generating predictions...")
    predictor = Predictor(history_path=str(Path(__file__).parent / "data/predictions_history.json"))
    predictions, changes = await predictor.predict_all(articles_by_category)
    logger.info(f"Generated {len(predictions)} predictions, {len(changes)} changes")
    
    # 生成今日概览
    summary_parts = []
    for category, articles in articles_by_category.items():
        if articles:
            summary_parts.append(f"• {articles[0].title_zh[:50]}")
    summary = "今日要闻：\n" + "\n".join(summary_parts[:5]) if summary_parts else "今日暂无重大新闻。"
    
    # 构建简报
    briefing = DailyBriefing(
        date=target_date,
        articles_by_category=articles_by_category,
        predictions=predictions,
        prediction_changes=changes,
        summary=summary
    )
    
    # Step 4: 生成 Markdown
    logger.info("Step 4: Generating Markdown...")
    md_generator = MarkdownGenerator(output_dir=str(Path(__file__).parent / "output"))
    md_path = md_generator.save(briefing)
    logger.info(f"Saved to {md_path}")
    
    # Step 5: 更新飞书文档
    feishu_url = None
    try:
        logger.info("Step 5: Creating Feishu document...")
        
        # 使用飞书 skill
        import sys
        sys.path.insert(0, "/workspace/openclaw/skills/feishu-doc-operations")
        from scripts.feishu_doc_operations import obtainIdaasClientId, obtainIdaasClientSecret, obtainUserName, main as feishu_main
        
        # 读取生成的 Markdown 内容
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # 创建飞书文档
        result = feishu_main({
            'action': 'write',
            'title': f'每日全球科技简报 - {target_date.strftime("%Y-%m-%d")}',
            'content': md_content,
            'client_id': obtainIdaasClientId(),
            'client_secret': obtainIdaasClientSecret(),
            'userName': obtainUserName()
        })
        
        if result.get('code') == 0:
            feishu_url = result['data']['url']
            logger.info(f"Feishu document created: {feishu_url}")
        else:
            logger.warning(f"Feishu creation failed: {result.get('msg')}")
            
    except Exception as e:
        logger.warning(f"Feishu update skipped: {e}")
    
    # 统计
    total = sum(len(articles) for articles in articles_by_category.values())
    categories_with_content = sum(1 for articles in articles_by_category.values() if articles)
    
    logger.info(f"""
===== Daily Briefing Complete =====
Date: {target_date.strftime('%Y-%m-%d')}
Total Articles: {total}
Categories: {categories_with_content}/12
Markdown: {md_path}
Feishu: {feishu_url or 'N/A'}
===================================
""")
    
    return {
        'markdown': str(md_path),
        'feishu': feishu_url,
        'total_articles': total,
        'categories': categories_with_content
    }


if __name__ == "__main__":
    result = asyncio.run(run_daily_briefing())
    if result:
        print(f"SUCCESS!")
        print(f"Markdown: {result.get('markdown')}")
        print(f"Feishu: {result.get('feishu')}")
        print(f"Articles: {result.get('total_articles')}")
        print(f"Categories: {result.get('categories')}/12")
    else:
        print("FAILED: No output generated")
        sys.exit(1)
