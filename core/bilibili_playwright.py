"""基于Playwright的B站爬虫实现 - 通过API拦截获取数据"""
import time
import random
import json
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from utils.logger import log
from utils.storage import StorageUtil


class BilibiliPlaywrightCrawler:
    """使用Playwright浏览器的B站爬虫"""

    PLATFORM_NAME = "bilibili"

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
            # B站API域名
            if 'bilibili.com' in url or 'bilivideo.com' in url or 'biliapi.com' in url:
                # 过滤掉非数据资源
                if any(x in url for x in ['.jpg', '.png', '.mp4', '.webp', '.gif', '.js', '.css', '.woff', '.m4s']):
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
                    'domain': '.bilibili.com',
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

            # B站视频数据结构
            # 1. 搜索结果 result 结构
            if 'result' in data:
                result = data['result']
                if isinstance(result, list):
                    for video in result:
                        video_info = self._parse_video_info(video)
                        videos.append(video_info)
                elif isinstance(result, dict):
                    # result 里面可能有 type 字段区分不同类型
                    if 'video' in result or 'search_result' in result:
                        video_list = result.get('video', result.get('search_result', []))
                        for video in video_list:
                            video_info = self._parse_video_info(video)
                            videos.append(video_info)

            # 2. data.result 结构
            if 'data' in data:
                inner_data = data['data']
                if isinstance(inner_data, dict):
                    # 搜索API返回结构
                    if 'result' in inner_data:
                        result = inner_data['result']
                        if isinstance(result, list):
                            for video in result:
                                video_info = self._parse_video_info(video)
                                videos.append(video_info)
                        elif isinstance(result, dict):
                            for key in ['video', 'media_bangumi', 'media_ft']:
                                if key in result and isinstance(result[key], list):
                                    for video in result[key]:
                                        video_info = self._parse_video_info(video)
                                        videos.append(video_info)

                    # 用户投稿视频列表
                    if 'list' in inner_data and 'vlist' in inner_data['list']:
                        vlist = inner_data['list']['vlist']
                        for video in vlist:
                            video_info = self._parse_user_video_info(video)
                            videos.append(video_info)

                    # archives 结构
                    if 'archives' in inner_data:
                        archives = inner_data['archives']
                        for video in archives:
                            video_info = self._parse_video_info(video)
                            videos.append(video_info)

                    # 单个视频信息
                    if 'View' in inner_data:
                        video_info = self._parse_video_detail(inner_data['View'])
                        videos.append(video_info)

                    if 'arc' in inner_data:
                        video_info = self._parse_video_info(inner_data['arc'])
                        videos.append(video_info)

                if isinstance(inner_data, list):
                    for video in inner_data:
                        video_info = self._parse_video_info(video)
                        videos.append(video_info)

        # 去重
        seen_ids = set()
        unique_videos = []
        for v in videos:
            if v['bvid'] and v['bvid'] not in seen_ids:
                seen_ids.add(v['bvid'])
                unique_videos.append(v)

        log.info(f"从API提取到 {len(unique_videos)} 个唯一视频")
        return unique_videos

    def _parse_video_info(self, video):
        """解析单个视频信息"""
        # B站搜索结果中的视频结构
        author = video.get('author', '')
        if not author:
            # 尝试其他字段
            owner = video.get('owner', {})
            author = owner.get('name', video.get('name', ''))

        bvid = video.get('bvid', '')
        if not bvid:
            avid = video.get('aid', video.get('id', 0))
            if avid:
                bvid = self._aid_to_bvid(avid)

        stat = video.get('stat', video.get('statistics', {}))
        if not stat:
            stat = {
                'view': video.get('play', video.get('click', 0)),
                'like': video.get('like', 0),
                'comment': video.get('comment', 0),
                'favorite': video.get('favorite', video.get('collect', 0)),
            }

        return {
            'bvid': bvid,
            'aid': video.get('aid', video.get('id', 0)),
            'title': video.get('title', ''),
            'description': video.get('description', video.get('desc', '')),
            'author': author,
            'author_id': video.get('mid', video.get('userId', owner.get('mid', ''))),
            'video_url': f"https://www.bilibili.com/video/{bvid}",
            'duration': video.get('duration', video.get('length', '')),
            'view_count': stat.get('view', video.get('play', 0)),
            'like_count': stat.get('like', 0),
            'comment_count': stat.get('comment', 0),
            'favorite_count': stat.get('favorite', video.get('collect', 0)),
            'share_count': stat.get('share', 0),
            'pubdate': video.get('pubdate', video.get('pub_time', video.get('created', 0))),
        }

    def _parse_user_video_info(self, video):
        """解析用户投稿视频信息"""
        bvid = video.get('bvid', '')
        if not bvid:
            avid = video.get('aid', 0)
            if avid:
                bvid = self._aid_to_bvid(avid)

        return {
            'bvid': bvid,
            'aid': video.get('aid', 0),
            'title': video.get('title', ''),
            'description': video.get('description', ''),
            'author': video.get('author', ''),
            'author_id': video.get('mid', ''),
            'video_url': f"https://www.bilibili.com/video/{bvid}",
            'duration': video.get('length', ''),
            'view_count': video.get('play', 0),
            'like_count': video.get('video_review', 0),  # B站历史字段命名
            'comment_count': video.get('comment', 0),
            'favorite_count': video.get('favorites', 0),
            'share_count': 0,
            'pubdate': video.get('created', 0),
        }

    def _parse_video_detail(self, video):
        """解析视频详情"""
        owner = video.get('owner', {})
        stat = video.get('stat', {})

        return {
            'bvid': video.get('bvid', ''),
            'aid': video.get('aid', 0),
            'title': video.get('title', ''),
            'description': video.get('desc', ''),
            'author': owner.get('name', ''),
            'author_id': owner.get('mid', ''),
            'video_url': f"https://www.bilibili.com/video/{video.get('bvid', '')}",
            'duration': video.get('duration', 0),
            'view_count': stat.get('view', 0),
            'like_count': stat.get('like', 0),
            'comment_count': stat.get('reply', 0),
            'favorite_count': stat.get('favorite', 0),
            'share_count': stat.get('share', 0),
            'pubdate': video.get('pubdate', video.get('ctime', 0)),
        }

    def _aid_to_bvid(self, aid):
        """将AVID转换为BVID（简化版本）"""
        # B站的BV号算法比较复杂，这里简化处理
        # 如果API返回中没有bvid，说明数据可能不完整
        try:
            aid = int(aid)
            # 简单映射（实际算法更复杂）
            table = 'fZodR9XQDSUm21yCkr6zBqiveYah8btIgxs4LV9MA7Q'
            tr = {}
            for i, c in enumerate(table):
                tr[c] = i
            # 简化转换，实际可能不准确
            return f"BV{aid % 1000000000}"
        except:
            return ''

    def _extract_comments_from_api(self, video_id):
        """从捕获的API响应中提取评论数据"""
        comments = []
        for resp in self.api_responses:
            data = resp['data']
            url = resp['url']

            # B站评论API URL包含 'reply'
            if 'reply' in url.lower():
                # 检查API响应是否成功
                if data.get('code') != 0:
                    continue

                # B站评论数据结构: data.data.replies
                if 'data' in data:
                    inner_data = data['data']

                    if isinstance(inner_data, dict):
                        # 主评论列表
                        if 'replies' in inner_data:
                            replies = inner_data['replies']
                            if replies and isinstance(replies, list):
                                for reply in replies:
                                    comment_info = self._parse_comment_info(reply, video_id)
                                    comments.append(comment_info)
                                log.info(f"从API提取到 {len(replies)} 条评论")

                        # 热门评论
                        if 'hots' in inner_data:
                            hots = inner_data['hots']
                            if hots and isinstance(hots, list):
                                for hot in hots:
                                    comment_info = self._parse_comment_info(hot, video_id)
                                    comments.append(comment_info)

                        # 置顶评论 (top_replies 或 upper)
                        if 'top_replies' in inner_data and inner_data['top_replies']:
                            top = inner_data['top_replies']
                            if isinstance(top, list):
                                for t in top:
                                    comment_info = self._parse_comment_info(t, video_id)
                                    comments.append(comment_info)

                        if 'upper' in inner_data and inner_data['upper']:
                            upper = inner_data['upper']
                            if isinstance(upper, dict):
                                comment_info = self._parse_comment_info(upper, video_id)
                                comments.append(comment_info)

        return comments

    def _parse_comment_info(self, comment, video_id):
        """解析单个评论信息"""
        member = comment.get('member', {})

        return {
            'video_id': video_id,
            'comment_id': comment.get('rpid', comment.get('id', 0)),
            'author': member.get('uname', member.get('name', '')),
            'author_id': member.get('mid', 0),
            'text': comment.get('content', {}).get('message', comment.get('message', '')),
            'like_count': comment.get('like', 0),
            'reply_count': comment.get('rcount', 0),
            'ctime': comment.get('ctime', comment.get('time', 0)),
            'type': comment.get('type', 1),  # 1为一级评论
        }

    def search_videos(self, keyword, page_count=10, callback=None):
        """搜索视频 - B站搜索数据嵌入在DOM中"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        videos = []

        try:
            log.info("访问B站首页...")
            self.page.goto("https://www.bilibili.com", timeout=30000, wait_until="domcontentloaded")
            time.sleep(3)

            search_url = f"https://search.bilibili.com/all?keyword={keyword}"
            log.info(f"搜索关键词: {keyword}")
            self.page.goto(search_url, timeout=30000, wait_until="networkidle")

            log.info("等待数据加载...")
            time.sleep(5)

            # B站搜索数据嵌入在DOM中，从视频链接元素提取
            videos = self._extract_videos_from_dom()
            log.info(f"从DOM提取到 {len(videos)} 个视频")

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(4)

                # 滚动后再次从DOM提取
                new_videos = self._extract_videos_from_dom()
                # 只添加新视频
                for v in new_videos:
                    if v['bvid'] not in [x['bvid'] for x in videos]:
                        videos.append(v)

                if callback:
                    callback(i + 1, page_count, len(videos))

            # 去重
            seen_ids = set()
            unique_videos = []
            for v in videos:
                if v['bvid'] and v['bvid'] not in seen_ids:
                    seen_ids.add(v['bvid'])
                    unique_videos.append(v)

            log.info(f"共找到 {len(unique_videos)} 个视频")
            return unique_videos

        except Exception as e:
            log.error(f"搜索视频失败: {e}")
            return []

    def _extract_videos_from_dom(self):
        """从页面DOM元素提取视频数据"""
        videos = []
        import re

        try:
            # B站搜索结果在 .bili-video-card 容器中
            video_cards = self.page.locator('.bili-video-card').all()

            for card in video_cards:
                try:
                    # 从卡片中找视频链接
                    link = card.locator('a[href*="/video/BV"]').first
                    if link.count() == 0:
                        continue

                    href = link.evaluate('el => el.href')
                    match = re.search(r'video/(BV[A-Za-z0-9]+)', href)
                    if not match:
                        continue

                    bvid = match.group(1)

                    # 从 .bili-video-card__info--tit 获取标题
                    title_elem = card.locator('.bili-video-card__info--tit').first
                    title = ''
                    if title_elem.count() > 0:
                        # 优先使用 title 属性，否则使用 textContent
                        title = title_elem.evaluate('el => el.getAttribute("title") || el.textContent')

                    # 从 .bili-video-card__info--author 获取作者
                    author_elem = card.locator('.bili-video-card__info--author').first
                    author = ''
                    if author_elem.count() > 0:
                        author_text = author_elem.evaluate('el => el.textContent')
                        # 清理文本，去除前缀符号
                        author = author_text.strip().replace('Python学习教程-', '').strip()

                    # 从 .bili-video-card__stats--item 获取播放量
                    stats_items = card.locator('.bili-video-card__stats--item').all()
                    view_count = 0
                    danmaku_count = 0
                    if len(stats_items) >= 2:
                        # 第一个是播放量
                        view_text = stats_items[0].evaluate('el => el.textContent')
                        view_count = self._parse_stat_number(view_text)
                        # 第二个是弹幕数
                        danmaku_text = stats_items[1].evaluate('el => el.textContent')
                        danmaku_count = self._parse_stat_number(danmaku_text)

                    video_info = {
                        'bvid': bvid,
                        'aid': 0,
                        'title': title.strip()[:100] if title else '',
                        'description': '',
                        'author': author.strip() if author else '',
                        'author_id': '',
                        'video_url': f"https://www.bilibili.com/video/{bvid}",
                        'duration': '',
                        'view_count': view_count,
                        'like_count': 0,
                        'comment_count': 0,
                        'danmaku_count': danmaku_count,
                        'favorite_count': 0,
                        'share_count': 0,
                        'pubdate': 0,
                    }

                    videos.append(video_info)

                except Exception as e:
                    pass

        except Exception as e:
            log.error(f"从DOM提取失败: {e}")

        return videos

    def _parse_stat_number(self, text):
        """解析B站统计数字（如 207万、126）"""
        import re
        text = text.strip()
        if not text:
            return 0

        # 匹配数字和单位
        match = re.match(r'([\d.]+)(万)?', text)
        if match:
            num = float(match.group(1))
            if match.group(2) == '万':
                return int(num * 10000)
            return int(num)

        # 尝试直接解析数字
        try:
            return int(text)
        except:
            return 0

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

            # B站评论需要滚动到评论区域才会触发API
            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页评论")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(random.uniform(3, 5))

            # 滚动完成后等待API响应
            time.sleep(3)

            # 从捕获的API提取评论
            comments = self._extract_comments_from_api(video_id)
            log.info(f"提取到 {len(comments)} 条评论")

            if callback:
                callback(page_count, page_count, len(comments))

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
        """从URL提取视频ID（BV号或AVID）"""
        import re
        # BV号格式
        match = re.search(r'video/(BV[A-Za-z0-9]+)', url)
        if match:
            return match.group(1)
        # AVID格式
        match = re.search(r'video/av(\d+)', url)
        if match:
            return f"av{match.group(1)}"
        return None

    def get_user_posts(self, user_url, page_count=10, callback=None):
        """获取用户主页视频"""
        if not self.browser:
            self.start_browser()

        self.api_responses = []
        posts = []

        try:
            log.info(f"访问用户主页: {user_url}")
            self.page.goto(user_url, timeout=60000, wait_until="networkidle")

            log.info("等待视频数据加载...")
            time.sleep(5)

            for i in range(page_count):
                if not self.is_running:
                    break

                log.info(f"滚动加载第 {i+1} 页视频")
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
                if p['bvid'] not in seen_ids:
                    seen_ids.add(p['bvid'])
                    unique_posts.append(p)

            log.info(f"共获取 {len(unique_posts)} 个视频")
            return unique_posts

        except Exception as e:
            log.error(f"获取视频失败: {e}")
            return []

    def _get_video_fields(self):
        """视频数据字段"""
        return ['序号', '视频ID(BV号)', '视频地址', '标题', '作者', '作者ID',
                '时长', '播放量', '点赞数', '评论数', '收藏数', '转发数', '发布时间']

    def _get_comment_fields(self):
        """评论数据字段"""
        return ['序号', '评论ID', '视频地址', '评论内容', '评论者', '评论者ID', '点赞数', '回复数', '发布时间']

    def _format_video_for_export(self, video, index):
        """格式化视频数据用于导出"""
        pubdate = video.get('pubdate', 0)
        if pubdate:
            if pubdate > 10000000000:
                pubdate = pubdate / 1000
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(pubdate))
        else:
            publish_time = ''

        duration = video.get('duration', '')
        if isinstance(duration, int):
            # 转换为 mm:ss 格式
            minutes = duration // 60
            seconds = duration % 60
            duration = f"{minutes}:{seconds:02d}"

        return {
            '序号': index,
            '视频ID(BV号)': video.get('bvid', ''),
            '视频地址': video.get('video_url', ''),
            '标题': video.get('title', '')[:100] if video.get('title') else '',
            '作者': video.get('author', ''),
            '作者ID': video.get('author_id', ''),
            '时长': duration,
            '播放量': video.get('view_count', 0),
            '点赞数': video.get('like_count', 0),
            '评论数': video.get('comment_count', 0),
            '收藏数': video.get('favorite_count', 0),
            '转发数': video.get('share_count', 0),
            '发布时间': publish_time,
        }

    def _format_comment_for_export(self, comment, index):
        """格式化评论数据用于导出"""
        ctime = comment.get('ctime', 0)
        if ctime:
            if ctime > 10000000000:
                ctime = ctime / 1000
            publish_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(ctime))
        else:
            publish_time = ''

        video_id = comment.get('video_id', '')
        video_url = f"https://www.bilibili.com/video/{video_id}" if video_id else ''

        return {
            '序号': index,
            '评论ID': comment.get('comment_id', ''),
            '视频地址': video_url,
            '评论内容': comment.get('text', ''),
            '评论者': comment.get('author', ''),
            '评论者ID': comment.get('author_id', ''),
            '点赞数': comment.get('like_count', 0),
            '回复数': comment.get('reply_count', 0),
            '发布时间': publish_time,
        }

    def search_and_collect_videos(self, keyword, page_count=10, per_page=20, callback=None):
        """搜索关键词并采集视频数据"""
        videos = self.search_videos(keyword, page_count=page_count, callback=callback)

        if videos:
            formatted_videos = [self._format_video_for_export(v, i+1) for i, v in enumerate(videos)]
            filename = self.storage.get_timestamp_filename('bili_search_videos')
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
            filename = self.storage.get_timestamp_filename('bili_search_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(total_comments, filename)

        self.total_count = len(total_comments)
        return len(total_comments)

    def collect_comments_from_video(self, video_url, page_count=10, per_page=20, callback=None):
        """从指定视频链接采集评论"""
        comments = self.get_video_comments(video_url, page_count=page_count, callback=callback)

        if comments:
            formatted_comments = [self._format_comment_for_export(c, i+1) for i, c in enumerate(comments)]
            filename = self.storage.get_timestamp_filename('bili_comments')
            self.storage.save_csv(formatted_comments, filename, self._get_comment_fields())
            self.storage.save_json(comments, filename)

        self.total_count = len(comments)
        return len(comments)

    def collect_user_posts(self, user_url, page_count=10, per_page=20, callback=None):
        """采集用户主页视频"""
        posts = self.get_user_posts(user_url, page_count=page_count, callback=callback)

        if posts:
            formatted_posts = [self._format_video_for_export(p, i+1) for i, p in enumerate(posts)]
            filename = self.storage.get_timestamp_filename('bili_posts')
            self.storage.save_csv(formatted_posts, filename, self._get_video_fields())
            self.storage.save_json(posts, filename)

        self.total_count = len(posts)
        return len(posts)