# 📰 每日全球科技简报

AI驱动的全球科技新闻聚合与分析平台。

![Daily Briefing](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 🌟 功能

- 📰 **全球新闻采集** - 覆盖中国、美国、日本、韩国、欧洲等主要科技媒体
- 🌐 **自动翻译** - 多语言新闻自动翻译为中文
- 🏷️ **智能分类** - 12大类别自动分类
- 🔄 **智能去重** - 保留首发+重要补充，避免重复
- 🎤 **关键人物追踪** - 识别并高亮科技大佬发言
- 🔮 **未来预测** - 各领域1周/1月/半年/1年预测
- 📝 **多格式输出** - 飞书文档 + Markdown

## 新闻分类

1. 🤖 AI类
2. 🦾 机器人类
3. 👓 具身智能类
4. 💾 半导体行业类
5. 🚗 汽车类
6. 🏥 健康医疗类
7. 📊 经济政策类
8. 💼 商业科技类
9. 🏛️ 政治政策类
10. 📈 投资财经类
11. 📱 消费电子类
12. 🎤 关键人物发言

## 新闻源

覆盖 70+ 全球科技媒体，包括：

- **中国**: 36氪、虎嗅、钛媒体、机器之心、量子位、财新等
- **美国**: TechCrunch、The Verge、Wired、Bloomberg、Reuters等
- **日本**: 日经、ITmedia等
- **韩国**: 韩联社、ETNews等
- **欧洲**: The Register、Tech.eu、Heise等
- **东南亚**: Tech in Asia、e27等

## 安装

```bash
# 克隆项目
cd /workspace/daily-briefing

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 配置

### 环境变量

```bash
# LLM API (选择一个)
export ANTHROPIC_API_KEY="your-key"
# 或
export OPENAI_API_KEY="your-key"

# 飞书 (可选)
export FEISHU_APP_ID="your-app-id"
export FEISHU_APP_SECRET="your-app-secret"
```

### 配置文件

- `config/sources.yaml` - 新闻源配置
- `config/categories.yaml` - 分类配置
- `config/key_people.yaml` - 关键人物配置

## 使用

### 手动运行

```bash
# 生成昨天的简报
python src/main.py

# 指定日期
python src/main.py --date 2026-02-13

# 跳过飞书文档生成
python src/main.py --skip-feishu
```

### 自动化 (OpenClaw Cron)

每天早上6点自动运行，10点前完成。

## 输出

### Markdown 文件

输出到 `output/briefing_YYYYMMDD.md`

### 飞书文档

自动追加到指定的飞书文档（需配置飞书应用）

## 架构

```
daily-briefing/
├── config/
│   ├── sources.yaml      # 新闻源配置
│   ├── categories.yaml   # 分类配置
│   └── key_people.yaml   # 关键人物配置
├── src/
│   ├── main.py           # 主程序
│   ├── models.py         # 数据模型
│   ├── collector.py      # 新闻采集
│   ├── processor.py      # 新闻处理
│   ├── predictor.py      # 预测生成
│   ├── generator.py      # 文档生成
│   └── feishu_client.py  # 飞书API
├── data/
│   └── predictions_history.json  # 预测历史
├── output/               # 输出目录
├── logs/                 # 日志目录
└── requirements.txt      # 依赖
```

## 技术栈

- **采集**: feedparser, httpx, trafilatura, Playwright
- **处理**: LangChain, Claude/GPT-4
- **存储**: SQLite, JSON
- **输出**: 飞书SDK, Markdown

## 注意事项

1. 首次运行需要较长时间（采集+处理）
2. 建议配置代理以访问部分国外新闻源
3. LLM API调用有成本，注意用量
4. 部分网站可能需要特殊处理（反爬虫）

## 🌐 Web 界面

项目包含一个美观的 Web 界面，用于阅读简报。

### 本地运行

```bash
cd web
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5000

### 部署到 Render

1. Fork 本项目到你的 GitHub
2. 在 [Render.com](https://render.com) 创建新的 Web Service
3. 连接你的 GitHub 仓库
4. Render 会自动使用 `render.yaml` 配置进行部署

## 📝 License

MIT
