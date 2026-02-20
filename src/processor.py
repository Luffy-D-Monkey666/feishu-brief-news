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


class ClassificationCache:
    """分类缓存：基于标题关键词相似度复用分类结果"""
    
    def __init__(self, cache_path: str = "data/classification_cache.json", max_size: int = 1000):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """加载缓存"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    data = json.load(f)
                    # 只保留最近的条目
                    if len(data) > self.max_size:
                        sorted_items = sorted(data.items(), key=lambda x: x[1].get('used_at', ''), reverse=True)
                        data = dict(sorted_items[:self.max_size])
                    return data
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save classification cache: {e}")
    
    def _extract_keywords(self, title: str) -> set:
        """提取标题关键词"""
        import re
        # 移除标点和常见词
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 
                      'of', 'and', 'or', 'with', 'as', 'by', 'from', 'its', 'it', 'this', 'that',
                      '的', '是', '在', '和', '了', '与', '将', '为', '被', '对', '等', '个'}
        # 提取词汇（英文按空格分，中文按字符）
        words = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]+', title.lower())
        keywords = {w for w in words if len(w) > 1 and w not in stop_words}
        return keywords
    
    def _calc_similarity(self, kw1: set, kw2: set) -> float:
        """计算关键词相似度（Jaccard）"""
        if not kw1 or not kw2:
            return 0.0
        intersection = len(kw1 & kw2)
        union = len(kw1 | kw2)
        return intersection / union if union > 0 else 0.0
    
    def get_cached_category(self, title: str, threshold: float = 0.6) -> Optional[tuple[str, float]]:
        """尝试从缓存获取分类"""
        keywords = self._extract_keywords(title)
        if len(keywords) < 2:
            return None
        
        best_match = None
        best_similarity = 0.0
        
        for cached_title, data in self.cache.items():
            cached_kw = set(data.get('keywords', []))
            similarity = self._calc_similarity(keywords, cached_kw)
            
            if similarity > best_similarity and similarity >= threshold:
                best_similarity = similarity
                best_match = data
        
        if best_match:
            # 更新使用时间
            logger.debug(f"Cache hit for '{title[:30]}...' -> {best_match['category']} (sim={best_similarity:.2f})")
            return best_match['category'], best_match.get('confidence', 0.8) * best_similarity
        
        return None
    
    def add_to_cache(self, title: str, category: str, confidence: float):
        """添加分类结果到缓存"""
        keywords = self._extract_keywords(title)
        if len(keywords) < 2:
            return
        
        self.cache[title] = {
            'category': category,
            'confidence': confidence,
            'keywords': list(keywords),
            'used_at': datetime.now().isoformat()
        }
        
        # 定期保存（每10个新条目保存一次）
        if len(self.cache) % 10 == 0:
            self._save_cache()
    
    def save(self):
        """手动保存缓存"""
        self._save_cache()


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
        self.classification_cache = ClassificationCache()  # 新增：分类缓存
        
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
    
    async def translate_summarize_and_classify(self, article: RawArticle) -> dict:
        """翻译、生成摘要并分类（合并为一次LLM调用，节省token）"""
        
        system_prompt = """你是一位专业的科技新闻编辑。你的任务是：
1. 将新闻标题翻译成中文（如已是中文则保持原样）
2. 生成详细的中文摘要（3-5段，包含所有关键信息）
3. 提取3-5个关键要点
4. 分析这条新闻的行业影响
5. 对文章进行分类

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

输出JSON格式，不要包含markdown标记。"""

        prompt = f"""请处理以下新闻：

标题: {article.title}
来源: {article.source}
发布时间: {article.published_at}
语言: {article.language}

正文:
{article.content[:5000] if article.content else '(无正文)'}

请输出JSON：
{{
    "title_zh": "中文标题",
    "summary_zh": "详细中文摘要（3-5段）",
    "key_points": ["要点1", "要点2", "要点3"],
    "impact_analysis": "对行业的影响分析",
    "category": "分类ID",
    "category_confidence": 0.95
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
                "impact_analysis": "",
                "category": "business",
                "category_confidence": 0.5
            }
    
    # 保留旧方法以兼容，但标记为废弃
    async def translate_and_summarize(self, article: RawArticle) -> dict:
        """[已废弃] 请使用 translate_summarize_and_classify"""
        result = await self.translate_summarize_and_classify(article)
        return {k: v for k, v in result.items() if k not in ['category', 'category_confidence']}
    
    async def classify(self, article: RawArticle, translation: dict) -> tuple[Category, float]:
        """[已废弃] 分类已合并到 translate_summarize_and_classify"""
        # 如果translation里已有分类信息，直接使用
        if 'category' in translation:
            try:
                return Category(translation['category']), translation.get('category_confidence', 0.8)
            except ValueError:
                pass
        
        # 否则单独调用（兼容旧代码）
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
        """处理单篇文章（优化版：合并翻译+摘要+分类为一次LLM调用，支持分类缓存）"""
        
        # 先尝试从缓存获取分类
        cached_category = self.classification_cache.get_cached_category(article.title)
        
        # 一次调用完成翻译、摘要和分类
        result = await self.translate_summarize_and_classify(article)
        
        # 解析分类（优先使用 LLM 结果，缓存作为参考）
        try:
            category = Category(result.get('category', 'business'))
            confidence = result.get('category_confidence', 0.8)
        except ValueError:
            # 如果 LLM 返回无效分类，尝试使用缓存
            if cached_category:
                try:
                    category = Category(cached_category[0])
                    confidence = cached_category[1]
                    logger.info(f"Using cached category for '{article.title[:30]}...': {category.value}")
                except ValueError:
                    category = Category.BUSINESS
                    confidence = 0.5
            else:
                category = Category.BUSINESS
                confidence = 0.5
        
        # 将分类结果添加到缓存
        self.classification_cache.add_to_cache(article.title, category.value, confidence)
        
        # 识别关键人物
        mentioned_people = self.identify_key_people(article, result)
        
        # 如果提到关键人物且是发言内容，改为key_people分类
        if mentioned_people and any(word in result.get('summary_zh', '') 
                                     for word in ['表示', '称', '认为', '宣布', '透露', '预测']):
            category = Category.KEY_PEOPLE
        
        return ProcessedArticle(
            id=article.id,
            title_original=article.title,
            title_zh=result.get('title_zh', article.title),
            url=article.url,
            source=article.source,
            published_at=article.published_at,
            category=category,
            category_confidence=confidence,
            summary_zh=result.get('summary_zh', ''),
            key_points=result.get('key_points', []),
            impact_analysis=result.get('impact_analysis', ''),
            images=article.image_urls,
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
        
        # 保存分类缓存
        self.classification_cache.save()
        
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
