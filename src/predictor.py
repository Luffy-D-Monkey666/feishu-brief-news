"""
Predictor - 预测模块

功能:
- 生成各领域未来预测（1周/1月/半年/1年）
- 对比历史预测，生成变化说明
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from models import Category, Prediction, PredictionChange, ProcessedArticle


class Predictor:
    """预测器"""
    
    def __init__(
        self,
        history_path: str = "data/predictions_history.json",
        llm_provider: str = "anthropic"
    ):
        self.history_path = Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()
        self.llm_provider = llm_provider
        self._init_llm()
        
    def _load_history(self) -> dict:
        """加载历史预测"""
        if self.history_path.exists():
            with open(self.history_path) as f:
                return json.load(f)
        return {}
    
    def _save_history(self):
        """保存预测历史"""
        with open(self.history_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2, default=str)
    
    def _init_llm(self):
        """初始化LLM客户端"""
        from llm_client import get_llm_client
        self.llm = get_llm_client(self.llm_provider)
    
    async def _call_llm(self, prompt: str, system: str = "") -> str:
        """调用LLM"""
        return await self.llm.chat(prompt, system)
    
    async def generate_predictions(
        self,
        category: Category,
        articles: list[ProcessedArticle]
    ) -> list[Prediction]:
        """为某个分类生成预测"""
        
        timeframes = [
            ("week", "未来一周"),
            ("month", "未来一个月"),
            ("half_year", "未来半年"),
            ("year", "未来一年")
        ]
        
        # 准备文章摘要
        articles_summary = "\n\n".join([
            f"- {a.title_zh}\n  摘要: {a.summary_zh[:300]}..."
            for a in articles[:20]  # 最多20篇
        ])
        
        category_info = {
            Category.AI: "AI与人工智能",
            Category.ROBOTICS: "机器人",
            Category.EMBODIED_AI: "具身智能",
            Category.SEMICONDUCTOR: "半导体",
            Category.AUTO: "汽车",
            Category.HEALTH: "健康医疗",
            Category.ECONOMY: "经济政策",
            Category.BUSINESS: "商业科技",
            Category.POLITICS: "政治政策",
            Category.INVESTMENT: "投资财经",
            Category.CONSUMER_ELECTRONICS: "消费电子",
            Category.KEY_PEOPLE: "关键人物动向"
        }
        
        system_prompt = f"""你是一位资深的{category_info[category]}行业分析师。
基于最新的新闻动态，你需要对该领域的未来发展做出专业预测。

预测要求：
1. 基于当前趋势和具体事件
2. 给出具体的预期事件或变化
3. 包含可能的风险和不确定性
4. 语言专业但易懂

输出纯文本，每个时间段2-4个要点。"""

        prompt = f"""以下是{category_info[category]}领域的最新新闻：

{articles_summary}

请分别预测：
1. 未来一周需要关注什么
2. 未来一个月需要关注什么
3. 未来半年需要关注什么
4. 未来一年需要关注什么

按以下JSON格式输出：
{{
    "week": "未来一周预测内容",
    "month": "未来一个月预测内容",
    "half_year": "未来半年预测内容",
    "year": "未来一年预测内容"
}}"""

        result = await self._call_llm(prompt, system_prompt)
        
        try:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1]
            if result.endswith("```"):
                result = result.rsplit("```", 1)[0]
            data = json.loads(result)
            
            predictions = []
            for timeframe, _ in timeframes:
                predictions.append(Prediction(
                    category=category,
                    timeframe=timeframe,
                    content=data.get(timeframe, ""),
                    created_at=datetime.now()
                ))
            
            return predictions
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse predictions for {category.value}")
            return []
    
    def compare_with_history(
        self,
        new_predictions: list[Prediction]
    ) -> list[PredictionChange]:
        """与历史预测对比，生成变化说明"""
        changes = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        for pred in new_predictions:
            key = f"{pred.category.value}_{pred.timeframe}"
            
            if key in self.history:
                old_pred = self.history[key]
                old_content = old_pred.get('content', '')
                
                # 简单对比：如果内容变化超过一定程度，记录变化
                if old_content != pred.content:
                    changes.append(PredictionChange(
                        category=pred.category,
                        timeframe=pred.timeframe,
                        old_content=old_content,
                        new_content=pred.content,
                        reason="根据最新新闻动态更新",  # TODO: 用LLM生成更详细的原因
                        changed_at=datetime.now()
                    ))
            
            # 更新历史
            self.history[key] = {
                'content': pred.content,
                'created_at': today
            }
        
        self._save_history()
        return changes
    
    async def generate_change_reasons(
        self,
        changes: list[PredictionChange],
        articles: list[ProcessedArticle]
    ) -> list[PredictionChange]:
        """用LLM生成预测变化的原因"""
        
        if not changes:
            return changes
        
        system_prompt = """你是一位分析师，需要解释预测发生变化的原因。
基于新旧预测内容和最新新闻，简要说明为什么预测发生了变化。
输出简洁的一句话原因。"""
        
        for change in changes:
            relevant_articles = [a for a in articles if a.category == change.category][:5]
            articles_text = "\n".join([f"- {a.title_zh}" for a in relevant_articles])
            
            prompt = f"""旧预测：{change.old_content[:500]}

新预测：{change.new_content[:500]}

相关新闻：
{articles_text}

请用一句话解释预测变化的原因："""
            
            reason = await self._call_llm(prompt, system_prompt)
            if reason:
                change.reason = reason.strip()
        
        return changes
    
    async def predict_all(
        self,
        articles_by_category: dict[Category, list[ProcessedArticle]]
    ) -> tuple[list[Prediction], list[PredictionChange]]:
        """为所有分类生成预测"""
        
        all_predictions = []
        
        for category, articles in articles_by_category.items():
            if not articles:
                continue
            
            predictions = await self.generate_predictions(category, articles)
            all_predictions.extend(predictions)
            logger.info(f"Generated predictions for {category.value}")
        
        # 对比历史，生成变化
        changes = self.compare_with_history(all_predictions)
        
        # 生成变化原因
        all_articles = [a for articles in articles_by_category.values() for a in articles]
        changes = await self.generate_change_reasons(changes, all_articles)
        
        return all_predictions, changes


async def main():
    """测试预测"""
    from models import ProcessedArticle
    
    # 模拟文章
    articles = [
        ProcessedArticle(
            id="test1",
            title_original="OpenAI releases GPT-5",
            title_zh="OpenAI发布GPT-5",
            url="https://example.com",
            source="TechCrunch",
            published_at=datetime.now(),
            category=Category.AI,
            category_confidence=0.95,
            summary_zh="OpenAI今日发布了其最新的大语言模型GPT-5...",
            key_points=["性能提升", "多模态能力"],
            impact_analysis="将推动AI应用发展",
            images=[],
            video_urls=[],
            language="en"
        )
    ]
    
    predictor = Predictor()
    predictions, changes = await predictor.predict_all({Category.AI: articles})
    
    for pred in predictions:
        print(f"\n[{pred.category.value}] {pred.timeframe}")
        print(pred.content)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
