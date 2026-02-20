"""
Generator - 文档生成模块

功能:
- 生成飞书文档
- 生成Markdown文件
- 上传图片
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from models import (
    Category, ProcessedArticle, Prediction, PredictionChange, DailyBriefing
)


CATEGORY_INFO = {
    Category.AI: {"name": "AI类", "icon": "🤖"},
    Category.ROBOTICS: {"name": "机器人类", "icon": "🦾"},
    Category.EMBODIED_AI: {"name": "具身智能类", "icon": "👓"},
    Category.SEMICONDUCTOR: {"name": "半导体行业类", "icon": "💾"},
    Category.AUTO: {"name": "汽车类", "icon": "🚗"},
    Category.HEALTH: {"name": "健康医疗类", "icon": "🏥"},
    Category.ECONOMY: {"name": "经济政策类", "icon": "📊"},
    Category.BUSINESS: {"name": "商业科技类", "icon": "💼"},
    Category.POLITICS: {"name": "政治政策类", "icon": "🏛️"},
    Category.INVESTMENT: {"name": "投资财经类", "icon": "📈"},
    Category.CONSUMER_ELECTRONICS: {"name": "消费电子类", "icon": "📱"},
    Category.KEY_PEOPLE: {"name": "关键人物发言", "icon": "🎤"},
}


class MarkdownGenerator:
    """Markdown生成器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _format_article(self, article: ProcessedArticle, index: int) -> str:
        """格式化单篇文章"""
        parts = []
        
        # 双语标题
        parts.append(f"### {index}. {article.title_original}")
        parts.append(f"### {article.title_zh}")
        parts.append("")
        
        # 元信息
        parts.append(f"**来源:** {article.source} | **时间:** {article.published_at.strftime('%Y-%m-%d %H:%M')}")
        parts.append("")
        
        # 提及的关键人物
        if article.mentioned_people:
            parts.append(f"**提及人物:** {', '.join(article.mentioned_people)}")
            parts.append("")
        
        # 详细摘要
        parts.append("**📰 详细摘要:**")
        parts.append("")
        parts.append(article.summary_zh)
        parts.append("")
        
        # 关键要点
        if article.key_points:
            parts.append("**🔑 关键要点:**")
            for point in article.key_points:
                parts.append(f"- {point}")
            parts.append("")
        
        # 影响分析
        if article.impact_analysis:
            parts.append("**📈 影响分析:**")
            parts.append(article.impact_analysis)
            parts.append("")
        
        # 原文链接
        parts.append(f"**🔗 原文链接:** [{article.url}]({article.url})")
        parts.append("")
        
        # 图片
        if article.images:
            parts.append("**🖼️ 相关图片:**")
            for img in article.images[:3]:  # 最多3张
                parts.append(f"![]({img})")
            parts.append("")
        
        # 视频
        if article.video_urls:
            parts.append("**📹 相关视频:**")
            for video in article.video_urls[:2]:  # 最多2个
                parts.append(f"- {video}")
            parts.append("")
        
        # 分隔线
        parts.append("---")
        parts.append("")
        
        return "\n".join(parts)
    
    def _format_predictions(
        self,
        predictions: list[Prediction],
        changes: list[PredictionChange]
    ) -> str:
        """格式化预测部分"""
        parts = []
        
        timeframe_names = {
            "week": "📆 未来一周关注点",
            "month": "📆 未来一个月关注点",
            "half_year": "📆 未来半年关注点",
            "year": "📆 未来一年关注点"
        }
        
        for timeframe, name in timeframe_names.items():
            parts.append(f"### {name}")
            parts.append("")
            parts.append("| 领域 | 预测关注 | 变化说明 |")
            parts.append("|------|----------|----------|")
            
            tf_predictions = [p for p in predictions if p.timeframe == timeframe]
            tf_changes = {c.category: c for c in changes if c.timeframe == timeframe}
            
            for pred in tf_predictions:
                info = CATEGORY_INFO[pred.category]
                change = tf_changes.get(pred.category)
                
                # 截断内容以适应表格
                content = pred.content[:100] + "..." if len(pred.content) > 100 else pred.content
                content = content.replace("\n", " ").replace("|", "\\|")
                
                if change:
                    change_note = f"⬆️ {change.reason[:30]}..." if len(change.reason) > 30 else f"⬆️ {change.reason}"
                else:
                    change_note = "—"
                
                parts.append(f"| {info['icon']} {info['name']} | {content} | {change_note} |")
            
            parts.append("")
        
        return "\n".join(parts)
    
    def generate(self, briefing: DailyBriefing) -> str:
        """生成完整的Markdown文档"""
        parts = []
        
        # 标题
        parts.append("# 📰 全球科技简报")
        parts.append("")
        
        # 日期分隔
        date_str = briefing.date.strftime("%Y年%m月%d日（%A）")
        parts.append("━" * 50)
        parts.append(f"## 📅 {date_str}")
        parts.append("━" * 50)
        parts.append("")
        
        # 今日概览
        parts.append("## 📊 今日概览")
        parts.append("")
        
        total = sum(len(articles) for articles in briefing.articles_by_category.values())
        parts.append(f"**共计 {total} 条新闻**")
        parts.append("")
        
        for category, articles in briefing.articles_by_category.items():
            if articles:
                info = CATEGORY_INFO[category]
                parts.append(f"- {info['icon']} {info['name']}: {len(articles)}条")
        parts.append("")
        
        if briefing.summary:
            parts.append("**今日要点:**")
            parts.append(briefing.summary)
            parts.append("")
        
        parts.append("━" * 50)
        parts.append("")
        
        # 各分类新闻
        for category in Category:
            articles = briefing.articles_by_category.get(category, [])
            if not articles:
                continue
            
            info = CATEGORY_INFO[category]
            parts.append(f"## {info['icon']} {info['name']}")
            parts.append("")
            
            for i, article in enumerate(articles, 1):
                parts.append(self._format_article(article, i))
        
        # 预测部分
        parts.append("━" * 50)
        parts.append("")
        parts.append("## 🎯 未来预测")
        parts.append("")
        parts.append(self._format_predictions(
            briefing.predictions,
            briefing.prediction_changes
        ))
        
        # 生成时间
        parts.append("━" * 50)
        parts.append("")
        parts.append(f"*生成时间: {briefing.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        parts.append("")
        
        return "\n".join(parts)
    
    def save(self, briefing: DailyBriefing, filename: Optional[str] = None) -> Path:
        """保存Markdown文件"""
        if filename is None:
            filename = f"briefing_{briefing.date.strftime('%Y%m%d')}.md"
        
        content = self.generate(briefing)
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Saved markdown to {filepath}")
        return filepath


class FeishuGenerator:
    """飞书文档生成器"""
    
    def __init__(self):
        # TODO: 初始化飞书SDK
        self.doc_id = None
        
    async def create_or_get_doc(self, title: str) -> str:
        """创建或获取飞书文档"""
        # TODO: 实现飞书API调用
        # 如果文档已存在，返回doc_id
        # 如果不存在，创建新文档
        pass
    
    async def append_content(self, doc_id: str, content: str):
        """向文档追加内容"""
        # TODO: 实现飞书API调用
        pass
    
    async def upload_image(self, image_path: str) -> str:
        """上传图片到飞书"""
        # TODO: 实现飞书API调用
        # 返回图片token
        pass
    
    async def generate(self, briefing: DailyBriefing) -> str:
        """生成飞书文档"""
        # TODO: 完整实现
        # 1. 获取或创建文档
        # 2. 上传图片
        # 3. 构建飞书文档块
        # 4. 追加内容
        
        logger.info("Feishu document generation - TODO")
        return ""


async def main():
    """测试生成"""
    from models import DailyBriefing, ProcessedArticle, Prediction, PredictionChange
    
    # 模拟数据
    article = ProcessedArticle(
        id="test1",
        title_original="OpenAI releases GPT-5 with revolutionary capabilities",
        title_zh="OpenAI发布具有革命性能力的GPT-5",
        url="https://techcrunch.com/2026/02/13/openai-gpt5",
        source="TechCrunch",
        published_at=datetime(2026, 2, 13, 9, 30),
        category=Category.AI,
        category_confidence=0.95,
        summary_zh="""OpenAI今日正式发布了其最新一代大语言模型GPT-5，这是继GPT-4之后的又一次重大飞跃。

新模型在多个关键指标上实现了显著提升：推理能力提升了40%，多模态理解能力增强了60%，同时将响应延迟降低了50%。

GPT-5最引人注目的新特性是其"持续学习"能力，能够在与用户的交互过程中不断优化自身表现，同时保持隐私安全。

此外，GPT-5还引入了全新的"代理模式"（Agent Mode），允许模型自主执行复杂的多步骤任务，这被视为向AGI迈进的重要一步。

业内分析师认为，GPT-5的发布将进一步加速AI技术在各行业的应用落地，同时也将加剧科技巨头之间的AI竞赛。""",
        key_points=[
            "推理能力提升40%，多模态能力提升60%",
            "引入'持续学习'能力",
            "全新'代理模式'支持复杂任务自主执行",
            "响应延迟降低50%"
        ],
        impact_analysis="GPT-5的发布将推动AI应用进入新阶段，预计将加速企业AI转型进程，同时可能引发新一轮AI监管讨论。",
        images=["https://example.com/gpt5-launch.jpg"],
        video_urls=["https://youtube.com/watch?v=example"],
        language="en",
        mentioned_people=["Sam Altman"]
    )
    
    prediction = Prediction(
        category=Category.AI,
        timeframe="week",
        content="关注GPT-5发布后的市场反应和竞争对手回应；Google可能加速Gemini 2.0发布计划。",
        created_at=datetime.now()
    )
    
    change = PredictionChange(
        category=Category.AI,
        timeframe="week",
        old_content="等待OpenAI新模型发布消息",
        new_content="关注GPT-5发布后的市场反应",
        reason="GPT-5已正式发布，关注重点转向市场反应",
        changed_at=datetime.now()
    )
    
    briefing = DailyBriefing(
        date=datetime(2026, 2, 13),
        articles_by_category={Category.AI: [article]},
        predictions=[prediction],
        prediction_changes=[change],
        summary="今日最重要新闻：OpenAI发布GPT-5，标志着AI能力的又一次重大突破。"
    )
    
    # 生成Markdown
    md_gen = MarkdownGenerator()
    filepath = md_gen.save(briefing)
    print(f"Generated: {filepath}")
    
    # 打印预览
    content = md_gen.generate(briefing)
    print(content[:2000])


if __name__ == "__main__":
    asyncio.run(main())
