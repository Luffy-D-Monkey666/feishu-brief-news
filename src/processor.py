"""
News Processor - 新闻处理模块

功能:
- 翻译（英文/日文/韩文 -> 中文）
- 分类
- 摘要生成
- 去重
- 关键人物识别
"""

import asyncio
import json
from datetime import datetime
from typing import Optional
import yaml
from pathlib import Path
from loguru import logger
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from models import (
    RawArticle, ProcessedArticle, Category, NewsEvent
)


class NewsProcessor:
    """新闻处理器"""
    
    def __init__(
        self,
        categories_config: str = "config/categories.yaml",
        people_config: str = "config/key_people.yaml",
        llm_provider: str = None  # auto-detect
    ):
        self.categories = self._load_categories(categories_config)
        self.key_people = self._load_key_people(people_config)
        self.embeddings_cache = {}
        
        # 初始化LLM客户端
        from llm_client import get_llm_client
        self.llm = get_llm_client(llm_provider)
        
    def _load_categories(self, config_path: str) -> dict:
        """加载分类配置"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return {c['id']: c for c in config['categories']}
    
    def _load_key_people(self, config_path: str) -> list[dict]:
        """加载关键人物配置"""
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return config['tech_leaders']
    
    async def _call_llm(self, prompt: str, system: str = "") -> str:
        """调用LLM"""
        return await self.llm.chat(prompt, system)
    
    async def translate_and_summarize(self, article: RawArticle) -> dict:
        """翻译并生成摘要"""
        
        system_prompt = """你是一位专业的科技新闻编辑和翻译。你的任务是：
1. 将新闻标题翻译成中文（如已是中文则保持原样）
2. 生成详细的中文摘要（3-5段，包含所有关键信息）
3. 提取3-5个关键要点
4. 分析这条新闻的行业影响

输出JSON格式，不要包含markdown标记。"""

        prompt = f"""请处理以下新闻：

标题: {article.title}
来源: {article.source}
发布时间: {article.published_at}
语言: {article.language}

正文:
{article.content[:8000] if article.content else '(无正文)'}

请输出JSON：
{{
    "title_zh": "中文标题",
    "summary_zh": "详细中文摘要（3-5段）",
    "key_points": ["要点1", "要点2", "要点3"],
    "impact_analysis": "对行业的影响分析"
}}"""

        result = await self._call_llm(prompt, system_prompt)
        
        try:
            # 清理可能的markdown标记
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response for {article.id}")
            return {
                "title_zh": article.title,
                "summary_zh": article.content[:500] if article.content else "",
                "key_points": [],
                "impact_analysis": ""
            }
    
    async def classify(self, article: RawArticle, translation: dict) -> tuple[Category, float]:
        """对文章进行分类"""
        
        system_prompt = """你是一位新闻分类专家。根据文章内容，选择最合适的分类。

可选分类：
- ai: AI类（AI技术、Agent、AI Coding、新功能）
- robotics: 机器人类（人形机器人、工业机器人、军用机器人）
- embodied_ai: 具身智能类（AI眼镜、可穿戴设备、新型交互）
- semiconductor: 半导体行业类（芯片、存储、制程、设备）
- auto: 汽车类（新能源车、燃油车、自动驾驶）
- health: 健康医疗类（生物科技、医疗器械、制药）
- economy: 经济政策类（宏观经济、产业政策、贸易）
- business: 商业科技类（企业动态、并购、融资）
- politics: 政治政策类（科技监管、地缘政治）
- investment: 投资财经类（股市、风投、IPO）
- consumer_electronics: 消费电子类（手机、电脑、智能家居）
- key_people: 关键人物发言（科技大佬观点和预测）

只输出JSON，不要其他内容。"""

        prompt = f"""标题: {article.title}
中文标题: {translation.get('title_zh', '')}
摘要: {translation.get('summary_zh', '')[:1000]}

请输出JSON：
{{"category": "分类ID", "confidence": 0.95}}"""

        result = await self._call_llm(prompt, system_prompt)
        
        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            data = json.loads(result)
            category = Category(data['category'])
            confidence = float(data.get('confidence', 0.8))
            return category, confidence
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to classify {article.id}: {e}")
            return Category.BUSINESS, 0.5
    
    def identify_key_people(self, article: RawArticle, translation: dict) -> list[str]:
        """识别文章中提到的关键人物"""
        mentioned = []
        
        content = f"{article.title} {translation.get('title_zh', '')} {translation.get('summary_zh', '')}"
        content_lower = content.lower()
        
        for person in self.key_people:
            # 检查英文名
            if person.get('name') and person['name'].lower() in content_lower:
                mentioned.append(person['name'])
                continue
            # 检查中文名
            if person.get('name_zh') and person['name_zh'] in content:
                mentioned.append(person.get('name') or person['name_zh'])
                continue
            # 检查中文名（作为name字段）
            if 'name_en' in person and person.get('name') in content:
                mentioned.append(person['name'])
                continue
        
        return list(set(mentioned))
    
    async def get_embedding(self, text: str) -> np.ndarray:
        """获取文本嵌入向量（用于去重）"""
        # 简化版：使用hash作为伪嵌入
        # 实际生产应该使用sentence-transformers或OpenAI embeddings
        
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]
        
        # 简单的词袋模型模拟
        words = set(text.lower().split())
        vec = np.array([hash(w) % 1000 for w in list(words)[:100]])
        vec = np.pad(vec, (0, max(0, 100 - len(vec))))
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        
        self.embeddings_cache[text] = vec
        return vec
    
    async def deduplicate(self, articles: list[ProcessedArticle], threshold: float = 0.85) -> list[ProcessedArticle]:
        """去重：保留首发 + 重要补充"""
        if not articles:
            return []
        
        # 按时间排序
        articles.sort(key=lambda x: x.published_at)
        
        # 计算嵌入
        embeddings = []
        for article in articles:
            text = f"{article.title_original} {article.title_zh}"
            emb = await self.get_embedding(text)
            embeddings.append(emb)
        
        embeddings = np.array(embeddings)
        
        # 标记重复
        unique_articles = []
        seen_events = []  # (embedding, event_id)
        
        for i, article in enumerate(articles):
            is_duplicate = False
            related_event_id = None
            
            for event_emb, event_id in seen_events:
                similarity = cosine_similarity([embeddings[i]], [event_emb])[0][0]
                if similarity > threshold:
                    is_duplicate = True
                    related_event_id = event_id
                    break
            
            if is_duplicate:
                # 标记为非首发，但检查是否有新信息
                article.is_primary = False
                article.related_event_id = related_event_id
                
                # 如果内容显著更长或来源更权威，仍然保留
                if len(article.summary_zh) > 1000:  # 有重要补充
                    unique_articles.append(article)
            else:
                # 首发
                article.is_primary = True
                event_id = article.id
                seen_events.append((embeddings[i], event_id))
                unique_articles.append(article)
        
        logger.info(f"Deduplicated: {len(articles)} -> {len(unique_articles)} articles")
        return unique_articles
    
    async def process_article(self, article: RawArticle) -> ProcessedArticle:
        """处理单篇文章"""
        # 翻译和摘要
        translation = await self.translate_and_summarize(article)
        
        # 分类
        category, confidence = await self.classify(article, translation)
        
        # 识别关键人物
        mentioned_people = self.identify_key_people(article, translation)
        
        # 如果提到关键人物且是发言内容，改为key_people分类
        if mentioned_people and any(word in translation.get('summary_zh', '') 
                                     for word in ['表示', '称', '认为', '宣布', '透露', '预测']):
            category = Category.KEY_PEOPLE
        
        return ProcessedArticle(
            id=article.id,
            title_original=article.title,
            title_zh=translation.get('title_zh', article.title),
            url=article.url,
            source=article.source,
            published_at=article.published_at,
            category=category,
            category_confidence=confidence,
            summary_zh=translation.get('summary_zh', ''),
            key_points=translation.get('key_points', []),
            impact_analysis=translation.get('impact_analysis', ''),
            images=article.image_urls,  # TODO: 下载到本地
            video_urls=article.video_urls,
            language=article.language,
            mentioned_people=mentioned_people
        )
    
    async def process_all(self, articles: list[RawArticle]) -> list[ProcessedArticle]:
        """处理所有文章"""
        # 限制并发
        semaphore = asyncio.Semaphore(5)
        
        async def process_with_semaphore(article):
            async with semaphore:
                try:
                    return await self.process_article(article)
                except Exception as e:
                    logger.error(f"Failed to process {article.id}: {e}")
                    return None
        
        tasks = [process_with_semaphore(a) for a in articles]
        results = await asyncio.gather(*tasks)
        
        processed = [r for r in results if r is not None]
        logger.info(f"Processed {len(processed)}/{len(articles)} articles")
        
        # 去重
        processed = await self.deduplicate(processed)
        
        return processed


async def main():
    """测试处理"""
    from collector import NewsCollector
    from datetime import timedelta
    
    collector = NewsCollector()
    since = datetime.now() - timedelta(days=1)
    articles = await collector.collect_all(since)
    await collector.close()
    
    processor = NewsProcessor()
    processed = await processor.process_all(articles[:5])  # 测试5篇
    
    for article in processed:
        print(f"\n{'='*60}")
        print(f"[{article.category.value}] {article.title_original}")
        print(f"中文: {article.title_zh}")
        print(f"来源: {article.source}")
        print(f"人物: {article.mentioned_people}")
        print(f"\n摘要:\n{article.summary_zh[:500]}...")


if __name__ == "__main__":
    asyncio.run(main())
