"""基于Playwright的抖音爬虫实现 - 通过API拦截获取数据"""
import time
import random
import json
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from utils.logger import log
from utils.storage import StorageUtil
from utils.parser import ParserUtil


class DouyinPlaywrightCrawler:
    """使用Playwright浏览器的抖音爬虫"""

    PLATFORM_NAME = "douyin"

    def __init__(self, cookie=None):
        self.storage = StorageUtil()
        self.cookie = cookie
        self.browser = None
        self.context = None
        self.page = None
        self.is_running = True
        self.total_count = 0
        self.api_responses = []  # 存储捕获的API响应

    def start_browser(self):
        """启动浏览器"""
        log.info("启动浏览器...")
        self.playwright = sync_playwright().start()
        # 使用非无头模式，添加反检测参数
        self.browser = self.playwright.chromium.launch(
            headless=False,  # 非无头模式
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-first-run',
                '--no-default-browser-check',
            ]
        )

        # 创建更真实的浏览器上下文
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
        )

        # 注入Cookie到浏览器上下文
        if self.cookie:
            log.info("正在注入Cookie...")
            cookies = self._parse_cookie_string(self.cookie)
            self.context.add_cookies(cookies)
            log.info(f"已注入 {len(cookies)} 个Cookie项")

        self.page = self.context.new_page()

        # 设置API响应监听
        self._setup_api_listener()

        log.info("浏览器已启动")

    def _setup_api_listener(self):
        """设置API响应监听器"""
        self.api_responses = []

        def handle_response(response):
            url = response.url
            # 扩大API匹配范围 - 抖音的API路径变化很大
            # 匹配抖音常见的API域名和路径
            if 'douyin.com' in url or 'snssdk.com' in url or 'bytedance.com' in url:
                # 过滤掉非数据API（图片、视频流等）
                if any(x in url for x in ['.jpg', '.png', '.mp4', '.webp', '.gif', '.js', '.css']):
                    return

                try:
                    # 尝试解析JSON
                    body = response.json()
                    if body and isinstance(body, dict):
                        self.api_responses.append({
                            'url': url,
                            'status': response.status,
                            'data': body
                        })
                        log.info(f"捕获API: {url[:100]}")
                except:
                    pass

        self.page.on('response', handle_response)

    def _parse_cookie_string(self, cookie_str):
        """解析Cookie字符串为Playwright格式"""
        cookies = []
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookies.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'domain': '.douyin.com',
                    'path': '/'
                })
        return cookies

    def stop(self):
        """停止采集"""
        self.is_running = False

    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
        log.info("浏览器已关闭")

    def _extract_videos_from_api(self):
        """从捕获的API响应中提取视频数据"""
        videos = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            # 检查各种可能的数据结构
            # 1. 直接有 aweme_list
            if 'aweme_list' in data:
                aweme_list = data['aweme_list']
                for aweme in aweme_list:
                    video_info = self._parse_aweme_info(aweme)
                    videos.append(video_info)

            # 2. data 字段包含数据
            if 'data' in data:
                inner_data = data['data']

                # 2a. data 是字典且有 aweme_list
                if isinstance(inner_data, dict) and 'aweme_list' in inner_data:
                    aweme_list = inner_data['aweme_list']
                    for aweme in aweme_list:
                        video_info = self._parse_aweme_info(aweme)
                        videos.append(video_info)

                # 2b. data 是列表（搜索API返回 data.data[] 结构）
                if isinstance(inner_data, list):
                    for item in inner_data:
                        # 搜索结果结构: data.data[].aweme_info
                        if 'aweme_info' in item:
                            aweme = item['aweme_info']
                            video_info = self._parse_aweme_info(aweme)
                            videos.append(video_info)
                        # 其他结构: data.data[] 直接是视频
                        elif 'aweme_id' in item:
                            video_info = self._parse_aweme_info(item)
                            videos.append(video_info)

            # 3. 搜索API的 feed 结构
            if 'aweme_info' in data:
                video_info = self._parse_aweme_info(data['aweme_info'])
                videos.append(video_info)

        # 去重
        seen_ids = set()
        unique_videos = []
        for v in videos:
            if v['aweme_id'] and v['aweme_id'] not in seen_ids:
                seen_ids.add(v['aweme_id'])
                unique_videos.append(v)

        log.info(f"从API提取到 {len(unique_videos)} 个唯一视频")
        return unique_videos

    def _parse_aweme_info(self, aweme):
        """解析单个视频信息"""
        author = aweme.get('author', {})
        statistics = aweme.get('statistics', {})

        return {
            'aweme_id': aweme.get('aweme_id', ''),
            'desc': aweme.get('desc', ''),
            'title': aweme.get('desc', '')[:100] if aweme.get('desc') else '',
            'author': author.get('nickname', ''),
            'author_id': author.get('unique_id', '') or author.get('uid', ''),
            'video_url': f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
            'like_count': statistics.get('digg_count', 0),
            'comment_count': statistics.get('comment_count', 0),
            'share_count': statistics.get('share_count', 0),
            'collect_count': statistics.get('collect_count', 0),
            'create_time': aweme.get('create_time', 0),
        }

    def _extract_comments_from_api(self, video_id):
        """从捕获的API响应中提取评论数据"""
        comments = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            # 检查是否是评论API
            if 'comment' in url.lower():
                if 'comments' in data:
                    comment_list = data['comments']
                    for comment in comment_list:
                        comment_info = {
                            'video_id': video_id,
                            'comment_id': comment.get('cid', ''),
                            'author': comment.get('user', {}).get('nickname', ''),
                            'author_id': comment.get('user', {}).get('unique_id', ''),
                            'text': comment.get('text', ''),
                            'like_count': comment.get('digg_count', 0),
                            'create_time': comment.get('create_time', 0),
                        }
                        comments.append(comment_info)

                if 'data' in data and isinstance(data['data'], dict):
                    inner_data = data['data']
                    if 'comments' in inner_data:
                        comment_list = inner_data['comments']
                        for comment in comment_list:
                            comment_info = {
                                'video_id': video_id,
                                'comment_id': comment.get('cid', ''),
                                'author': comment.get('user', {}).get('nickname', ''),
                                'author_id': comment.get('user', {}).get('unique_id', ''),
                                'text': comment.get('text', ''),
                                'like_count': comment.get('digg_count', 0),
                                'create_time': comment.get('create_time', 0),
                            }
                            comments.append(comment_info)

        return comments

    def search_videos(self, keyword, page_count=10, callback=None):
        """搜索视频"""
        if not self.browser:
            self.start_browser()

        # 清空之前的API响应
        self.api_responses = []
        videos = []

        try:
            # 先访问首页建立cookie上下文
            log.info("访问首页...")
            self.page.goto("https://www.douyin.com", timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

            # 访问搜索页
            search_url = f"https://www.douyin.com/search/{keyword}"
            log.info(f"搜索关键词: {keyword}")
            self.page.goto(search_url, timeout=60000, wait_until="networkidle")

            # 等待数据加载
            log.info("等待数据加载...")
            time.sleep(10)

            # 滚动加载更多
            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                # 从API响应中提取视频
                current_videos = self._extract_videos_from_api()
                videos.extend(current_videos)

                if callback:
                    callback(i + 1, page_count, len(videos))

            # 去重
            seen_ids = set()
            unique_videos = []
            for v in videos:
                if v['aweme_id'] not in seen_ids:
                    seen_ids.add(v['aweme_id'])
                    unique_videos.append(v)

            log.info(f"共找到 {len(unique_videos)} 个视频")
            return unique_videos

        except Exception as e:
            log.error(f"搜索视频失败: {e}")
            return []

    def get_video_comments(self, video_url, page_count=10, callback=None):
        """获取视频评论"""
        if not self.browser:
            self.start_browser()

        # 清空之前的API响应
        self.api_responses = []
        comments = []

        try:
            video_id = ParserUtil.extract_video_id(video_url) or ''
            log.info(f"访问视频页面: {video_url}")
            self.page.goto(video_url, timeout=60000, wait_until="networkidle")

            # 等待数据加载
            log.info("等待评论数据加载...")
            time.sleep(5)

            # 滚动加载更多评论
            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页评论")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                # 从API响应中提取评论
                current_comments = self._extract_comments_from_api(video_id)
                comments.extend(current_comments)

                if callback:
                    callback(i + 1, page_count, len(comments))

            # 去重
            seen_ids = set()
            unique_comments = []
            for c in comments:
                if c['comment_id'] not in seen_ids:
                    seen_ids.add(c['comment_id'])
                    unique_comments.append(c)

            log.info(f"共获取 {len(unique_comments)} 条评论")
            return unique_comments

        except Exception as e:
            log.error(f"获取评论失败: {e}")
            return []

    def get_user_posts(self, user_url, page_count=10, callback=None):
        """获取用户主页作品"""
        if not self.browser:
            self.start_browser()

        # 清空之前的API响应
        self.api_responses = []
        posts = []

        try:
            log.info(f"访问用户主页: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="networkidle")

            # 等待数据加载
            log.info("等待作品数据加载...")
            time.sleep(5)

            # 滚动加载更多
            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页作品")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                # 从API响应中提取视频
                current_posts = self._extract_videos_from_api()
                posts.extend(current_posts)

                if callback:
                    callback(i + 1, page_count, len(posts))

            # 去重
            seen_ids = set()
            unique_posts = []
            for p in posts:
                if p['aweme_id'] not in seen_ids:
                    seen_ids.add(p['aweme_id'])
                    unique_posts.append(p)

            log.info(f"共获取 {len(unique_posts)} 个作品")
            return unique_posts

        except Exception as e:
            log.error(f"获取作品失败: {e}")
            return []

    def _get_video_fields(self):
        """视频数据字段 - 适合人类阅读的顺序"""
        return ['序号', '视频ID', '视频地址', '标题', '作者', '作者ID',
                '点赞数', '评论数', '分享数', '收藏数', '发布时间']

    def _get_comment_fields(self):
        """评论数据字段 - 适合人类阅读的顺序"""
        return ['序号', '评论ID', '视频地址', '评论内容', '评论者', '评论者ID', '点赞数', '发布时间']

    def _format_video_for_export(self, video, index):
        """格式化视频数据用于导出"""
        import time
        create_time = video.get('create_time', 0)
        if create_time:
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(create_time))
        else:
            publish_time = ''

        return {
            '序号': index,
            '视频ID': video.get('aweme_id', ''),
            '视频地址': video.get('video_url', ''),
            '标题': video.get('title', '')[:100] if video.get('title') else '',
            '作者': video.get('author', ''),
            '作者ID': video.get('author_id', ''),
            '点赞数': video.get('like_count', 0),
            '评论数': video.get('comment_count', 0),
            '分享数': video.get('share_count', 0),
            '收藏数': video.get('collect_count', 0),
            '发布时间': publish_time,
        }

    def _format_comment_for_export(self, comment, index):
        """格式化评论数据用于导出"""
        import time
        create_time = comment.get('create_time', 0)
        if create_time:
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(create_time))
        else:
            publish_time = ''

        return {
            '序号': index,
            '评论ID': comment.get('comment_id', ''),
            '视频地址': f"https://www.douyin.com/video/{comment.get('video_id', '')}",
            '评论内容': comment.get('text', ''),
            '评论者': comment.get('author', ''),
            '评论者ID': comment.get('author_id', ''),
            '点赞数': comment.get('like_count', 0),
            '发布时间': publish_time,
        }

    def search_and_collect_videos(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集视频数据"""
        videos = self.search_videos(keyword, page_count=page_count, callback=callback)

        # 格式化并保存数据
        if videos:
            formatted_videos = [self._format_video_for_export(v, i+1) for i, v in enumerate(videos)]
            filename = self.storage.get_timestamp_filename('search_videos')
            self.storage.save_csv(formatted_videos, filename, self._get_video_fields())
            self.storage.save_json(videos, filename)

        self.total_count = len(videos)
        return len(videos)

    def search_and_collect_comments(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集评论"""
        if not self.browser:
            self.start_browser()

        # 先搜索视频
        videos = self.search_videos(keyword, page_count=min(page_count, 3), callback=None)

        if not videos:
            log.warning(f"搜索关键词 '{keyword}' 未找到视频")
            return 0

        log.info(f"找到 {len(videos)} 个视频，开始采集评论")

        total_comments = []
        for i, video in enumerate(videos[:min(len(videos), per_page)]):
            if not self.is_running:
                break

            video_url = video.get('video_url', '')
            if video_url:
                # 清空API响应
                self.api_responses = []

                comments = self.get_video_comments(video_url, page_count=2, callback=None)
                total_comments.extend(comments)

                if callback:
                    callback(i + 1, min(len(videos), per_page), len(total_comments))

                log.info(f"视频 {i + 1}/{min(len(videos), per_page)} 评论采集完成")

        # 格式化并保存数据
        if total_comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(total_comments)]
            filename = self.storage.get_timestamp_filename('search_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(total_comments, filename)

        self.total_count = len(total_comments)
        return len(total_comments)

    def collect_comments_from_video(self, video_url, page_count=10, per_page=20, callback=None):
        """从指定视频链接采集评论"""
        comments = self.get_video_comments(video_url, page_count=page_count, callback=callback)

        # 格式化并保存数据
        if comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(comments)]
            filename = self.storage.get_timestamp_filename('comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(comments, filename)

        self.total_count = len(comments)
        return len(comments)

    def collect_user_posts(self, user_url, page_count=10, per_page=20, callback=None):
        """采集用户主页作品"""
        posts = self.get_user_posts(user_url, page_count=page_count, callback=callback)

        # 格式化并保存数据
        if posts:
            formatted_posts = [self._format_video_for_export(p, i+1) for i, p in enumerate(posts)]
            filename = self.storage.get_timestamp_filename('posts')
            self.storage.save_csv(formatted_posts, filename, self._get_video_fields())
            self.storage.save_json(posts, filename)

        self.total_count = len(posts)
        return len(posts)