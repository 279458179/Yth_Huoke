"""基于Playwright的快手爬虫实现 - 通过API拦截获取数据"""
import time
import random
import json
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from utils.logger import log
from utils.storage import StorageUtil


class KuaishouPlaywrightCrawler:
    """使用Playwright浏览器的快手爬虫"""

    PLATFORM_NAME = "kuaishou"

    def __init__(self, cookie=None):
        self.storage = StorageUtil()
        self.cookie = cookie
        self.browser = None
        self.context = None
        self.page = None
        self.is_running = True
        self.total_count = 0
        self.api_responses = []

    def start_browser(self):
        """启动浏览器"""
        log.info("启动浏览器...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-first-run',
                '--no-default-browser-check',
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
        )

        if self.cookie:
            log.info("正在注入Cookie...")
            cookies = self._parse_cookie_string(self.cookie)
            self.context.add_cookies(cookies)
            log.info(f"已注入 {len(cookies)} 个Cookie项")

        self.page = self.context.new_page()
        self._setup_api_listener()
        log.info("浏览器已启动")

    def _setup_api_listener(self):
        """设置API响应监听器"""
        self.api_responses = []

        def handle_response(response):
            url = response.url
            if 'kuaishou.com' in url or 'gifshow.com' in url or 'kwai.com' in url:
                if any(x in url for x in ['.jpg', '.png', '.mp4', '.webp', '.gif', '.js', '.css']):
                    return

                try:
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
                    'domain': '.kuaishou.com',
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

            # 快手视频数据结构
            # 1. 搜索结果 feeds 结构
            if 'feeds' in data:
                feeds = data['feeds']
                for feed in feeds:
                    video_info = self._parse_feed_info(feed)
                    videos.append(video_info)

            # 2. photoList 结构
            if 'photoList' in data:
                photo_list = data['photoList']
                for photo in photo_list:
                    video_info = self._parse_feed_info(photo)
                    videos.append(video_info)

            # 3. data.feeds 结构
            if 'data' in data:
                inner_data = data['data']
                if isinstance(inner_data, dict):
                    if 'feeds' in inner_data:
                        feeds = inner_data['feeds']
                        for feed in feeds:
                            video_info = self._parse_feed_info(feed)
                            videos.append(video_info)

                    if 'photoList' in inner_data:
                        photo_list = inner_data['photoList']
                        for photo in photo_list:
                            video_info = self._parse_feed_info(photo)
                            videos.append(video_info)

                    # 单个视频结构
                    if 'photo' in inner_data:
                        video_info = self._parse_feed_info(inner_data['photo'])
                        videos.append(video_info)

                if isinstance(inner_data, list):
                    for item in inner_data:
                        if 'photo' in item:
                            video_info = self._parse_feed_info(item['photo'])
                            videos.append(video_info)
                        elif 'feed' in item:
                            video_info = self._parse_feed_info(item['feed'])
                            videos.append(video_info)

            # 4. photo 直接结构
            if 'photo' in data:
                video_info = self._parse_feed_info(data['photo'])
                videos.append(video_info)

        # 去重
        seen_ids = set()
        unique_videos = []
        for v in videos:
            if v['photo_id'] and v['photo_id'] not in seen_ids:
                seen_ids.add(v['photo_id'])
                unique_videos.append(v)

        log.info(f"从API提取到 {len(unique_videos)} 个唯一视频")
        return unique_videos

    def _parse_feed_info(self, feed):
        """解析单个视频信息"""
        # 快手数据结构: feed包含photo和author（author在顶层）
        photo = feed.get('photo', {})
        author = feed.get('author', {})  # author在feed顶层

        photo_id = photo.get('id', photo.get('photoId', ''))

        return {
            'photo_id': photo_id,
            'caption': photo.get('caption', ''),
            'title': photo.get('caption', '')[:100] if photo.get('caption') else '',
            'author': author.get('name', '') if author else '',
            'author_id': author.get('id', author.get('userId', '')) if author else '',
            'video_url': f"https://www.kuaishou.com/short-video/{photo_id}",
            'like_count': photo.get('likeCount', 0),
            'comment_count': photo.get('commentCount', 0),
            'share_count': photo.get('shareCount', 0),
            'view_count': photo.get('viewCount', 0),
            'timestamp': photo.get('timestamp', 0),
        }

    def _extract_comments_from_api(self, video_id):
        """从捕获的API响应中提取评论数据"""
        comments = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            if 'comment' in url.lower():
                # 快手评论数据结构: rootCommentsV2
                if 'rootCommentsV2' in data:
                    comment_list = data['rootCommentsV2']
                    for comment in comment_list:
                        comment_info = self._parse_comment_info(comment, video_id)
                        comments.append(comment_info)

                if 'comments' in data:
                    comment_list = data['comments']
                    for comment in comment_list:
                        comment_info = self._parse_comment_info(comment, video_id)
                        comments.append(comment_info)

                if 'data' in data and isinstance(data['data'], dict):
                    inner_data = data['data']
                    if 'rootCommentsV2' in inner_data:
                        comment_list = inner_data['rootCommentsV2']
                        for comment in comment_list:
                            comment_info = self._parse_comment_info(comment, video_id)
                            comments.append(comment_info)

                    if 'comments' in inner_data:
                        comment_list = inner_data['comments']
                        for comment in comment_list:
                            comment_info = self._parse_comment_info(comment, video_id)
                            comments.append(comment_info)

                    if 'list' in inner_data:
                        comment_list = inner_data['list']
                        for comment in comment_list:
                            comment_info = self._parse_comment_info(comment, video_id)
                            comments.append(comment_info)

                if 'list' in data:
                    comment_list = data['list']
                    for comment in comment_list:
                        comment_info = self._parse_comment_info(comment, video_id)
                        comments.append(comment_info)

        return comments

    def _parse_comment_info(self, comment, video_id):
        """解析单个评论信息"""
        # 快手评论结构：字段在顶层
        # content, author_name, author_id, comment_id, timestamp, likeCount
        return {
            'video_id': video_id,
            'comment_id': comment.get('comment_id', comment.get('id', comment.get('commentId', ''))),
            'author': comment.get('author_name', comment.get('name', '')),
            'author_id': comment.get('author_id', comment.get('userId', '')),
            'text': comment.get('content', comment.get('text', '')),
            'like_count': comment.get('likeCount', 0),
            'timestamp': comment.get('timestamp', 0),
        }

    def search_videos(self, keyword, page_count=10, callback=None):
        """搜索视频 - 快手PC端搜索功能可能受限，使用推荐页替代"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        videos = []

        try:
            log.info("访问快手首页...")
            self.page.goto("https://www.kuaishou.com", timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)

            # 快手PC端搜索功能可能被限制，改用推荐页
            log.info("访问推荐页面...")
            self.page.goto("https://www.kuaishou.com/new-reco", timeout=30000, wait_until="domcontentloaded")

            log.info("等待数据加载...")
            # 等待足够长时间让feed API响应被捕获
            for _ in range(10):  # 循环检查，最多等待10秒
                time.sleep(1)
                feed_count = len([r for r in self.api_responses if 'feeds' in r.get('data', {})])
                if feed_count > 0:
                    log.info(f"已捕获 {feed_count} 个feed API")
                    break

            # 提取已捕获的视频
            current_videos = self._extract_videos_from_api()
            videos.extend(current_videos)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')

                # 等待新数据加载
                for _ in range(5):  # 循环检查，最多等待5秒
                    time.sleep(1)
                    # 检查是否有新的feed API
                    feed_count = len([r for r in self.api_responses if 'feeds' in r.get('data', {})])
                    if feed_count > len(videos) // 20 + 1:  # 大约每页20个视频
                        break

                current_videos = self._extract_videos_from_api()
                videos.extend(current_videos)

                if callback:
                    callback(i + 1, page_count, len(videos))

            # 去重
            seen_ids = set()
            unique_videos = []
            for v in videos:
                if v['photo_id'] not in seen_ids:
                    seen_ids.add(v['photo_id'])
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

        self.api_responses = []
        comments = []

        try:
            video_id = self._extract_video_id(video_url) or ''
            log.info(f"访问视频页面: {video_url}")
            self.page.goto(video_url, timeout=60000, wait_until="networkidle")

            log.info("等待评论数据加载...")
            time.sleep(5)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页评论")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

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

    def _extract_video_id(self, url):
        """从URL提取视频ID"""
        import re
        match = re.search(r'short-video/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'photoId=([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        return None

    def get_user_posts(self, user_url, page_count=10, callback=None):
        """获取用户主页作品"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        posts = []

        try:
            log.info(f"访问用户主页: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="networkidle")

            log.info("等待作品数据加载...")
            time.sleep(5)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页作品")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                current_posts = self._extract_videos_from_api()
                posts.extend(current_posts)

                if callback:
                    callback(i + 1, page_count, len(posts))

            # 去重
            seen_ids = set()
            unique_posts = []
            for p in posts:
                if p['photo_id'] not in seen_ids:
                    seen_ids.add(p['photo_id'])
                    unique_posts.append(p)

            log.info(f"共获取 {len(unique_posts)} 个作品")
            return unique_posts

        except Exception as e:
            log.error(f"获取作品失败: {e}")
            return []

    def _get_video_fields(self):
        """视频数据字段"""
        return ['序号', '视频ID', '视频地址', '标题', '作者', '作者ID',
                '点赞数', '评论数', '分享数', '播放数', '发布时间']

    def _get_comment_fields(self):
        """评论数据字段"""
        return ['序号', '评论ID', '视频地址', '评论内容', '评论者', '评论者ID', '点赞数', '发布时间']

    def _format_video_for_export(self, video, index):
        """格式化视频数据用于导出"""
        timestamp = video.get('timestamp', 0)
        if timestamp:
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(timestamp / 1000 if timestamp > 10000000000 else timestamp))
        else:
            publish_time = ''

        return {
            '序号': index,
            '视频ID': video.get('photo_id', ''),
            '视频地址': video.get('video_url', ''),
            '标题': video.get('title', ''),
            '作者': video.get('author', ''),
            '作者ID': video.get('author_id', ''),
            '点赞数': video.get('like_count', 0),
            '评论数': video.get('comment_count', 0),
            '分享数': video.get('share_count', 0),
            '播放数': video.get('view_count', 0),
            '发布时间': publish_time,
        }

    def _format_comment_for_export(self, comment, index):
        """格式化评论数据用于导出"""
        timestamp = comment.get('timestamp', 0)
        if timestamp:
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(timestamp / 1000 if timestamp > 10000000000 else timestamp))
        else:
            publish_time = ''

        return {
            '序号': index,
            '评论ID': comment.get('comment_id', ''),
            '视频地址': f"https://www.kuaishou.com/short-video/{comment.get('video_id', '')}",
            '评论内容': comment.get('text', ''),
            '评论者': comment.get('author', ''),
            '评论者ID': comment.get('author_id', ''),
            '点赞数': comment.get('like_count', 0),
            '发布时间': publish_time,
        }

    def search_and_collect_videos(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集视频数据"""
        videos = self.search_videos(keyword, page_count=page_count, callback=callback)

        if videos:
            formatted_videos = [self._format_video_for_export(v, i+1) for i, v in enumerate(videos)]
            filename = self.storage.get_timestamp_filename('ks_search_videos')
            self.storage.save_csv(formatted_videos, filename, self._get_video_fields())
            self.storage.save_json(videos, filename)

        self.total_count = len(videos)
        return len(videos)

    def search_and_collect_comments(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集评论"""
        if not self.browser:
            self.start_browser()

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
                self.api_responses = []

                comments = self.get_video_comments(video_url, page_count=2, callback=None)
                total_comments.extend(comments)

                if callback:
                    callback(i + 1, min(len(videos), per_page), len(total_comments))

                log.info(f"视频 {i + 1}/{min(len(videos), per_page)} 评论采集完成")

        if total_comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(total_comments)]
            filename = self.storage.get_timestamp_filename('ks_search_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(total_comments, filename)

        self.total_count = len(total_comments)
        return len(total_comments)

    def collect_comments_from_video(self, video_url, page_count=10, per_page=20, callback=None):
        """从指定视频链接采集评论"""
        comments = self.get_video_comments(video_url, page_count=page_count, callback=callback)

        if comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(comments)]
            filename = self.storage.get_timestamp_filename('ks_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(comments, filename)

        self.total_count = len(comments)
        return len(comments)

    def collect_user_posts(self, user_url, page_count=10, per_page=20, callback=None):
        """采集用户主页作品"""
        posts = self.get_user_posts(user_url, page_count=page_count, callback=callback)

        if posts:
            formatted_posts = [self._format_video_for_export(p, i+1) for i, p in enumerate(posts)]
            filename = self.storage.get_timestamp_filename('ks_posts')
            self.storage.save_csv(formatted_posts, filename, self._get_video_fields())
            self.storage.save_json(posts, filename)

        self.total_count = len(posts)
        return len(posts)