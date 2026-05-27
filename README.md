# 视频平台数据采集工具

一款通用的视频平台数据采集工具，支持抖音、快手、小红书、B站等平台的数据采集。

## 功能特性

- **搜索视频采集**：根据关键词搜索视频并采集视频数据
- **搜索评论采集**：根据关键词搜索视频并采集评论数据
- **作品链接评论采集**：直接根据作品链接采集评论
- **主页作品采集**：根据博主主页链接采集作品数据

## 支持平台

- ✅ 抖音（已实现）
- ✅ 快手（已实现）
- ✅ 小红书（已实现）
- ✅ B站（已实现）

## 安装使用

### 1. 环境要求

- Python 3.8+
- Playwright（用于浏览器自动化）

### 2. 安装依赖

```bash
pip install playwright
playwright install chromium
```

### 3. 获取Cookie

各平台Cookie获取方式：

**抖音：**
1. 打开浏览器访问 https://www.douyin.com
2. 登录抖音账号
3. 按 F12 打开开发者工具
4. 切换到 Network（网络）标签
5. 刷新页面，找到任意请求
6. 在请求头中找到 Cookie 字段，复制完整内容

**快手：**
1. 打开浏览器访问 https://www.kuaishou.com
2. 登录快手账号
3. 按上述步骤获取Cookie

**小红书：**
1. 打开浏览器访问 https://www.xiaohongshu.com
2. 登录小红书账号
3. 按上述步骤获取Cookie

**B站：**
1. 打开浏览器访问 https://www.bilibili.com
2. 登录B站账号
3. 按上述步骤获取Cookie

### 4. 配置Cookie

各平台使用独立的Cookie文件，格式如下：
- `cookie_douyin.txt` - 抖音Cookie
- `cookie_kuaishou.txt` - 快手Cookie
- `cookie_xiaohongshu.txt` - 小红书Cookie
- `cookie_bilibili.txt` - B站Cookie

在程序中：
1. 选择对应平台
2. 点击"Cookie配置"按钮，会自动打开/创建该平台的Cookie文件
3. 将Cookie粘贴到文件中保存
4. 点击"刷新Cookie"按钮加载最新Cookie

### 5. 运行程序

```bash
python main.py
```

## 使用说明

### 功能1：搜索评论采集

1. 选择平台：抖音
2. 选择功能：搜索评论采集
3. 输入搜索关键词（如：Python教程）
4. 设置采集页数和每页数量
5. 点击"开始采集"

### 功能2：作品链接评论采集

1. 选择功能：作品链接评论采集
2. 输入抖音作品链接（格式：https://www.douyin.com/video/xxx）
3. 点击"开始采集"

### 功能3：主页作品采集

1. 选择功能：主页作品采集
2. 输入博主主页链接（格式：https://www.douyin.com/user/xxx）
3. 点击"开始采集"

## 数据格式

采集结果保存在 `results/` 目录：

- **CSV格式**：`results/csv/` 目录，可用Excel打开
- **JSON格式**：`results/json/` 目录，便于程序处理

### 评论数据字段

| 字段 | 说明 |
|------|------|
| video_id | 视频ID |
| video_title | 视频标题 |
| video_link | 视频链接 |
| author_name | 评论者昵称 |
| author_id | 评论者ID |
| author_uid | 评论者UID |
| author_link | 评论者主页链接 |
| comment_time | 评论时间 |
| comment_ip | 评论IP属地 |
| comment_like | 评论点赞数 |
| comment_level | 评论级别 |
| comment_text | 评论内容 |

### 作品数据字段

| 字段 | 说明 |
|------|------|
| author_name | 作者昵称 |
| author_uid | 作者UID |
| author_fans | 作者粉丝数 |
| video_title | 视频标题 |
| video_tags | 视频标签 |
| video_link | 视频链接 |
| publish_time | 发布时间 |
| like_count | 点赞数 |
| comment_count | 评论数 |
| collect_count | 收藏数 |
| share_count | 转发数 |

## 注意事项

1. 本工具仅供学习研究使用，请遵守相关法律法规
2. 请合理设置采集频率，避免对平台造成压力
3. Cookie有效期有限，过期后需重新获取
4. 部分接口可能需要签名参数，如遇请求失败请检查Cookie是否有效

## 项目结构

```
Yth_Huoke/
├── main.py              # GUI主界面
├── config.py            # 配置文件
├── cookie.txt           # Cookie存储
├── core/
│   ├── base_crawler.py        # 爬虫基类
│   ├── douyin.py              # 抖音API实现（备用）
│   ├── douyin_playwright.py   # 抖音Playwright实现
│   ├── kuaishou_playwright.py # 快手Playwright实现
│   ├── xiaohongshu_playwright.py # 小红书Playwright实现
│   └── bilibili_playwright.py # B站Playwright实现
├── utils/
│   ├── request.py       # HTTP请求封装
│   ├── storage.py       # 数据存储
│   ├── logger.py        # 日志记录
│   └── parser.py        # 数据解析
├── logs/                # 日志目录
└── results/             # 结果目录
```

## 扩展开发

如需支持其他平台，继承 `BaseCrawler` 类并实现以下方法：

```python
class YourPlatformCrawler(BaseCrawler):
    def search_videos(self, keyword, page_count, per_page):
        # 实现搜索逻辑
        pass

    def get_comments(self, video_id, page_count, per_page):
        # 实现评论采集逻辑
        pass

    def get_user_posts(self, user_url, page_count, per_page):
        # 实现主页作品采集逻辑
        pass
```

## License

仅供学习研究使用，禁止用于商业用途。