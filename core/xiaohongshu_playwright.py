"""基于Playwright的小红书爬虫实现 - 通过API拦截获取数据"""
import time
import random
import json
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from utils.logger import log
from utils.storage import StorageUtil


class XiaohongshuPlaywrightCrawler:
    """使用Playwright浏览器的小红书爬虫"""

    PLATFORM_NAME = "xiaohongshu"

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
            # 小红书API域名 - 包括edith子域名
            if 'xiaohongshu.com' in url or 'xhscdn.com' in url:
                # 过滤掉非数据资源
                if any(x in url for x in ['.jpg', '.png', '.mp4', '.webp', '.gif', '.js', '.css', '.woff', '.jpeg']):
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
                    'domain': '.xiaohongshu.com',
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

    def _extract_notes_from_api(self):
        """从捕获的API响应中提取笔记数据"""
        notes = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            # 小红书搜索API: /api/sns/web/v1/search/notes
            # 返回结构: { code, success, msg, data: { has_more, items: [...] } }
            if 'data' in data and isinstance(data['data'], dict):
                inner_data = data['data']

                # 搜索结果 items 结构 (最重要)
                if 'items' in inner_data:
                    items = inner_data['items']
                    for item in items:
                        # item 结构: { note_card, id, model_type, xsec_token }
                        if 'note_card' in item:
                            note_info = self._parse_note_card(item['note_card'], item.get('id', ''))
                            notes.append(note_info)
                        elif 'id' in item:
                            # 直接解析item
                            note_info = self._parse_note_info(item)
                            notes.append(note_info)

                # feeds 结构 (主页)
                if 'feeds' in inner_data:
                    feeds = inner_data['feeds']
                    for feed in feeds:
                        if 'note_card' in feed:
                            note_info = self._parse_note_card(feed['note_card'], feed.get('id', ''))
                            notes.append(note_info)
                        elif 'note' in feed:
                            note_info = self._parse_note_info(feed['note'])
                            notes.append(note_info)

                # noteList 结构
                if 'noteList' in inner_data:
                    note_list = inner_data['noteList']
                    for note in note_list:
                        note_info = self._parse_note_info(note)
                        notes.append(note_info)

                # 单个笔记结构
                if 'note' in inner_data and 'note_card' not in inner_data:
                    note_info = self._parse_note_info(inner_data['note'])
                    notes.append(note_info)

            # 直接有 items (某些API)
            if 'items' in data and isinstance(data['items'], list):
                items = data['items']
                for item in items:
                    if 'note_card' in item:
                        note_info = self._parse_note_card(item['note_card'], item.get('id', ''))
                        notes.append(note_info)

            # 兼容旧结构
            if 'notes' in data:
                note_list = data['notes']
                for note in note_list:
                    note_info = self._parse_note_info(note)
                    notes.append(note_info)

            if 'feeds' in data:
                feeds = data['feeds']
                for feed in feeds:
                    if 'noteCard' in feed:
                        note_info = self._parse_note_info(feed['noteCard'])
                        notes.append(note_info)
                    elif 'note' in feed:
                        note_info = self._parse_note_info(feed['note'])
                        notes.append(note_info)

        # 去重
        seen_ids = set()
        unique_notes = []
        for n in notes:
            if n['note_id'] and n['note_id'] not in seen_ids:
                seen_ids.add(n['note_id'])
                unique_notes.append(n)

        log.info(f"从API提取到 {len(unique_notes)} 个唯一笔记")
        return unique_notes

    def _parse_note_card(self, note_card, note_id=''):
        """解析note_card结构（搜索结果中的主要结构）"""
        user = note_card.get('user', {})
        interact = note_card.get('interact_info', {})

        note_id = note_id or note_card.get('note_id', '')

        return {
            'note_id': note_id,
            'title': note_card.get('display_title', ''),
            'desc': note_card.get('desc', ''),
            'type': note_card.get('type', ''),
            'author': user.get('nick_name', user.get('nickname', '')),
            'author_id': user.get('user_id', ''),
            'note_url': f"https://www.xiaohongshu.com/explore/{note_id}",
            'like_count': int(interact.get('liked_count', 0) or 0),
            'comment_count': int(interact.get('comment_count', 0) or 0),
            'collect_count': int(interact.get('collected_count', 0) or 0),
            'share_count': int(interact.get('shared_count', 0) or 0),
            'time': note_card.get('time', 0),
        }

    def _parse_note_info(self, note):
        """解析单个笔记信息"""
        user = note.get('user', note.get('author', {}))

        return {
            'note_id': note.get('noteId', note.get('id', '')),
            'title': note.get('title', note.get('displayTitle', '')),
            'desc': note.get('desc', ''),
            'type': note.get('type', ''),
            'author': user.get('nickname', user.get('name', '')),
            'author_id': user.get('userId', user.get('id', '')),
            'note_url': f"https://www.xiaohongshu.com/explore/{note.get('noteId', note.get('id', ''))}",
            'like_count': note.get('likedCount', note.get('likes', 0)),
            'comment_count': note.get('commentsCount', note.get('comments', 0)),
            'collect_count': note.get('collectedCount', note.get('collects', 0)),
            'share_count': note.get('shareCount', 0),
            'time': note.get('time', note.get('createTime', 0)),
        }

    def _extract_comments_from_api(self, note_id):
        """从捕获的API响应中提取评论数据"""
        comments = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            if 'comment' in url.lower():
                # 小红书评论数据结构
                if 'comments' in data:
                    comment_list = data['comments']
                    for comment in comment_list:
                        comment_info = self._parse_comment_info(comment, note_id)
                        comments.append(comment_info)

                if 'data' in data and isinstance(data['data'], dict):
                    inner_data = data['data']
                    if 'comments' in inner_data:
                        comment_list = inner_data['comments']
                        for comment in comment_list:
                            comment_info = self._parse_comment_info(comment, note_id)
                            comments.append(comment_info)

                    if 'commentList' in inner_data:
                        comment_list = inner_data['commentList']
                        for comment in comment_list:
                            comment_info = self._parse_comment_info(comment, note_id)
                            comments.append(comment_info)

                if 'commentList' in data:
                    comment_list = data['commentList']
                    for comment in comment_list:
                        comment_info = self._parse_comment_info(comment, note_id)
                        comments.append(comment_info)

        return comments

    def _parse_comment_info(self, comment, note_id):
        """解析单个评论信息"""
        user = comment.get('user', comment.get('author', {}))
        return {
            'note_id': note_id,
            'comment_id': comment.get('id', comment.get('commentId', '')),
            'author': user.get('nickname', user.get('name', '')),
            'author_id': user.get('userId', user.get('id', '')),
            'text': comment.get('content', comment.get('text', '')),
            'like_count': comment.get('likeCount', comment.get('likes', 0)),
            'sub_comment_count': comment.get('subCommentCount', 0),
            'time': comment.get('time', comment.get('createTime', 0)),
        }

    def search_notes(self, keyword, page_count=10, callback=None):
        """搜索笔记"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        notes = []

        try:
            log.info("访问小红书首页...")
            self.page.goto("https://www.xiaohongshu.com", timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

            search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}"
            log.info(f"搜索关键词: {keyword}")
            self.page.goto(search_url, timeout=60000, wait_until="networkidle")

            log.info("等待数据加载...")
            time.sleep(8)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                current_notes = self._extract_notes_from_api()
                notes.extend(current_notes)

                if callback:
                    callback(i + 1, page_count, len(notes))

            # 去重
            seen_ids = set()
            unique_notes = []
            for n in notes:
                if n['note_id'] not in seen_ids:
                    seen_ids.add(n['note_id'])
                    unique_notes.append(n)

            log.info(f"共找到 {len(unique_notes)} 个笔记")
            return unique_notes

        except Exception as e:
            log.error(f"搜索笔记失败: {e}")
            return []

    def get_note_comments(self, note_url, page_count=10, callback=None):
        """获取笔记评论"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        comments = []

        try:
            note_id = self._extract_note_id(note_url) or ''
            log.info(f"访问笔记页面: {note_url}")
            self.page.goto(note_url, timeout=60000, wait_until="networkidle")

            log.info("等待评论数据加载...")
            time.sleep(5)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页评论")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                current_comments = self._extract_comments_from_api(note_id)
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

    def _extract_note_id(self, url):
        """从URL提取笔记ID"""
        import re
        match = re.search(r'explore/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'discovery/item/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'noteId=([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)
        return None

    def get_user_posts(self, user_url, page_count=10, callback=None):
        """获取用户主页笔记"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        posts = []

        try:
            log.info(f"访问用户主页: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="networkidle")

            log.info("等待笔记数据加载...")
            time.sleep(5)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页笔记")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

                current_posts = self._extract_notes_from_api()
                posts.extend(current_posts)

                if callback:
                    callback(i + 1, page_count, len(posts))

            # 去重
            seen_ids = set()
            unique_posts = []
            for p in posts:
                if p['note_id'] not in seen_ids:
                    seen_ids.add(p['note_id'])
                    unique_posts.append(p)

            log.info(f"共获取 {len(unique_posts)} 个笔记")
            return unique_posts

        except Exception as e:
            log.error(f"获取笔记失败: {e}")
            return []

    def _get_note_fields(self):
        """笔记数据字段"""
        return ['序号', '笔记ID', '笔记地址', '标题', '类型', '作者', '作者ID',
                '点赞数', '评论数', '收藏数', '分享数', '发布时间']

    def _get_comment_fields(self):
        """评论数据字段"""
        return ['序号', '评论ID', '笔记地址', '评论内容', '评论者', '评论者ID', '点赞数', '子评论数', '发布时间']

    def _format_note_for_export(self, note, index):
        """格式化笔记数据用于导出"""
        timestamp = note.get('time', 0)
        if timestamp:
            if timestamp > 10000000000:
                timestamp = timestamp / 1000
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(timestamp))
        else:
            publish_time = ''

        return {
            '序号': index,
            '笔记ID': note.get('note_id', ''),
            '笔记地址': note.get('note_url', ''),
            '标题': note.get('title', '')[:100] if note.get('title') else '',
            '类型': note.get('type', ''),
            '作者': note.get('author', ''),
            '作者ID': note.get('author_id', ''),
            '点赞数': note.get('like_count', 0),
            '评论数': note.get('comment_count', 0),
            '收藏数': note.get('collect_count', 0),
            '分享数': note.get('share_count', 0),
            '发布时间': publish_time,
        }

    def _format_comment_for_export(self, comment, index):
        """格式化评论数据用于导出"""
        timestamp = comment.get('time', 0)
        if timestamp:
            if timestamp > 10000000000:
                timestamp = timestamp / 1000
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(timestamp))
        else:
            publish_time = ''

        return {
            '序号': index,
            '评论ID': comment.get('comment_id', ''),
            '笔记地址': f"https://www.xiaohongshu.com/explore/{comment.get('note_id', '')}",
            '评论内容': comment.get('text', ''),
            '评论者': comment.get('author', ''),
            '评论者ID': comment.get('author_id', ''),
            '点赞数': comment.get('like_count', 0),
            '子评论数': comment.get('sub_comment_count', 0),
            '发布时间': publish_time,
        }

    def search_and_collect_videos(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集笔记数据"""
        notes = self.search_notes(keyword, page_count=page_count, callback=callback)

        if notes:
            formatted_notes = [self._format_note_for_export(n, i+1) for i, n in enumerate(notes)]
            filename = self.storage.get_timestamp_filename('xhs_search_notes')
            self.storage.save_csv(formatted_notes, filename, self._get_note_fields())
            self.storage.save_json(notes, filename)

        self.total_count = len(notes)
        return len(notes)

    def search_and_collect_comments(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集评论"""
        if not self.browser:
            self.start_browser()

        notes = self.search_notes(keyword, page_count=min(page_count, 3), callback=None)

        if not notes:
            log.warning(f"搜索关键词 '{keyword}' 未找到笔记")
            return 0

        log.info(f"找到 {len(notes)} 个笔记，开始采集评论")

        total_comments = []
        for i, note in enumerate(notes[:min(len(notes), per_page)]):
            if not self.is_running:
                break

            note_url = note.get('note_url', '')
            if note_url:
                self.api_responses = []

                comments = self.get_note_comments(note_url, page_count=2, callback=None)
                total_comments.extend(comments)

                if callback:
                    callback(i + 1, min(len(notes), per_page), len(total_comments))

                log.info(f"笔记 {i + 1}/{min(len(notes), per_page)} 评论采集完成")

        if total_comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(total_comments)]
            filename = self.storage.get_timestamp_filename('xhs_search_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(total_comments, filename)

        self.total_count = len(total_comments)
        return len(total_comments)

    def collect_comments_from_video(self, note_url, page_count=10, per_page=20, callback=None):
        """从指定笔记链接采集评论"""
        comments = self.get_note_comments(note_url, page_count=page_count, callback=callback)

        if comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(comments)]
            filename = self.storage.get_timestamp_filename('xhs_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(comments, filename)

        self.total_count = len(comments)
        return len(comments)

    def collect_user_posts(self, user_url, page_count=10, per_page=20, callback=None):
        """采集用户主页笔记"""
        posts = self.get_user_posts(user_url, page_count=page_count, callback=callback)

        if posts:
            formatted_posts = [self._format_note_for_export(p, i+1) for i, p in enumerate(posts)]
            filename = self.storage.get_timestamp_filename('xhs_posts')
            self.storage.save_csv(formatted_posts, filename, self._get_note_fields())
            self.storage.save_json(posts, filename)

        self.total_count = len(posts)
        return len(posts)