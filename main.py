"""视频平台数据采集工具 - GUI主界面"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import webbrowser
import os
import time

from config import COOKIE_FILE, PLATFORMS, FUNC_TYPES, DEFAULT_PAGE_COUNT, DEFAULT_PER_PAGE
from core import DouyinPlaywrightCrawler
from utils.logger import log


class CrawlerApp:
    """数据采集工具GUI应用"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("视频平台数据采集工具 v1.0")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # 爬虫实例
        self.crawler = None
        self.is_running = False
        self.cookie = ""

        # 初始化界面
        self._create_ui()
        self._load_cookie()

    def _create_ui(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === 顶部工具栏 ===
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=5)

        ttk.Button(toolbar, text="Cookie配置", command=self._open_cookie_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="查看日志", command=self._open_log_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="查看结果", command=self._open_result_dir).pack(side=tk.LEFT, padx=5)

        # === 平台选择 ===
        platform_frame = ttk.LabelFrame(main_frame, text="平台选择", padding="5")
        platform_frame.pack(fill=tk.X, pady=5)

        self.platform_var = tk.StringVar(value='douyin')
        for key, name in PLATFORMS.items():
            rb = ttk.Radiobutton(platform_frame, text=name, value=key, variable=self.platform_var)
            rb.pack(side=tk.LEFT, padx=10)

        # === 功能选择 ===
        func_frame = ttk.LabelFrame(main_frame, text="功能选择", padding="5")
        func_frame.pack(fill=tk.X, pady=5)

        self.func_var = tk.StringVar(value='search_videos')
        for key, name in FUNC_TYPES.items():
            rb = ttk.Radiobutton(func_frame, text=name, value=key, variable=self.func_var, command=self._on_func_change)
            rb.pack(side=tk.LEFT, padx=10)

        # === 输入区域 ===
        input_frame = ttk.LabelFrame(main_frame, text="输入参数", padding="5")
        input_frame.pack(fill=tk.X, pady=5)

        # 输入提示
        self.input_label = ttk.Label(input_frame, text="搜索关键词（如：Python教程）:")
        self.input_label.pack(anchor=tk.W)

        # 输入框
        self.input_entry = ttk.Entry(input_frame, width=60)
        self.input_entry.pack(fill=tk.X, pady=5)

        # 参数设置
        param_frame = ttk.Frame(input_frame)
        param_frame.pack(fill=tk.X, pady=5)

        ttk.Label(param_frame, text="采集页数:").pack(side=tk.LEFT)
        self.page_count_var = tk.StringVar(value=str(DEFAULT_PAGE_COUNT))
        ttk.Entry(param_frame, width=10, textvariable=self.page_count_var).pack(side=tk.LEFT, padx=5)

        ttk.Label(param_frame, text="每页数量:").pack(side=tk.LEFT, padx=20)
        self.per_page_var = tk.StringVar(value=str(DEFAULT_PER_PAGE))
        ttk.Entry(param_frame, width=10, textvariable=self.per_page_var).pack(side=tk.LEFT, padx=5)

        # === 操作按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="开始采集", command=self._start_crawl)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop_crawl, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT, padx=10)

        # === 进度显示 ===
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=500)
        self.progress_bar.pack(side=tk.LEFT, padx=5)

        self.progress_label = ttk.Label(progress_frame, text="等待开始...")
        self.progress_label.pack(side=tk.LEFT, padx=10)

        # === 日志输出 ===
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # === 底部状态 ===
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)

        # 版权信息
        ttk.Label(status_frame, text="仅供学习研究使用", foreground="gray").pack(side=tk.RIGHT)

    def _on_func_change(self):
        """功能切换时更新输入提示"""
        func = self.func_var.get()
        if func == 'search_videos':
            self.input_label.config(text="搜索关键词（如：Python教程）:")
        elif func == 'search_comments':
            self.input_label.config(text="搜索关键词（如：Python教程）:")
        elif func == 'video_comments':
            self.input_label.config(text="作品链接（如：https://www.douyin.com/video/xxx）:")
        elif func == 'user_posts':
            self.input_label.config(text="主页链接（如：https://www.douyin.com/user/xxx）:")

    def _load_cookie(self):
        """加载Cookie"""
        try:
            if os.path.exists(COOKIE_FILE):
                with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 跳过注释行和空行，找到实际的cookie
                    cookie_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            cookie_lines.append(line)

                    self.cookie = ''.join(cookie_lines).strip()
                    if self.cookie:
                        self._log(f"Cookie已加载（长度: {len(self.cookie)} 字符）")
                    else:
                        self._log("请先配置Cookie（点击 'Cookie配置' 按钮）")
        except Exception as e:
            self._log(f"Cookie加载失败: {e}")

    def _open_cookie_file(self):
        """打开Cookie文件"""
        if os.path.exists(COOKIE_FILE):
            webbrowser.open(COOKIE_FILE)
        else:
            messagebox.showinfo("提示", f"Cookie文件不存在: {COOKIE_FILE}")

    def _open_log_dir(self):
        """打开日志目录"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        if os.path.exists(log_dir):
            webbrowser.open(log_dir)
        else:
            messagebox.showinfo("提示", "日志目录暂无文件")

    def _open_result_dir(self):
        """打开结果目录"""
        result_dir = os.path.join(os.path.dirname(__file__), 'results')
        if os.path.exists(result_dir):
            webbrowser.open(result_dir)
        else:
            messagebox.showinfo("提示", "结果目录暂无文件")

    def _log(self, msg):
        """输出日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        log.info(msg)

    def _clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def _update_progress(self, current, total, count):
        """更新进度"""
        percent = (current / total) * 100 if total > 0 else 0
        self.progress_var.set(percent)
        self.progress_label.config(text=f"已采集: {count} 条")

    def _start_crawl(self):
        """开始采集"""
        # 检查Cookie
        if not self.cookie or self.cookie.startswith('#'):
            messagebox.showwarning("提示", "请先配置Cookie！")
            return

        # 获取输入
        input_text = self.input_entry.get().strip()
        if not input_text:
            messagebox.showwarning("提示", "请输入搜索内容或链接！")
            return

        # 获取参数
        try:
            page_count = int(self.page_count_var.get())
            per_page = int(self.per_page_var.get())
        except ValueError:
            messagebox.showwarning("提示", "页数和每页数量必须是数字！")
            return

        # 更新UI状态
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.progress_label.config(text="采集中...")

        # 在后台线程执行采集
        thread = threading.Thread(
            target=self._crawl_thread,
            args=(input_text, page_count, per_page),
            daemon=True
        )
        thread.start()

    def _crawl_thread(self, input_text, page_count, per_page):
        """采集线程"""
        try:
            # 创建爬虫实例
            platform = self.platform_var.get()
            if platform == 'douyin':
                self.crawler = DouyinPlaywrightCrawler(cookie=self.cookie)
            else:
                self._log(f"平台 {platform} 暂未实现")
                return

            func = self.func_var.get()

            if func == 'search_videos':
                self._log(f"开始搜索视频: {input_text}")
                count = self.crawler.search_and_collect_videos(
                    input_text,
                    page_count=page_count,
                    per_page=per_page,
                    callback=self._update_progress
                )
                self._log(f"视频采集完成，共 {count} 条")

            elif func == 'search_comments':
                self._log(f"开始搜索关键词: {input_text}")
                count = self.crawler.search_and_collect_comments(
                    input_text,
                    page_count=page_count,
                    per_page=per_page,
                    callback=self._update_progress
                )
                self._log(f"搜索评论采集完成，共 {count} 条")

            elif func == 'video_comments':
                self._log(f"开始采集视频评论: {input_text}")
                count = self.crawler.collect_comments_from_video(
                    input_text,
                    page_count=page_count,
                    per_page=per_page,
                    callback=self._update_progress
                )
                self._log(f"视频评论采集完成，共 {count} 条")

            elif func == 'user_posts':
                self._log(f"开始采集主页作品: {input_text}")
                count = self.crawler.collect_user_posts(
                    input_text,
                    page_count=page_count,
                    per_page=per_page,
                    callback=self._update_progress
                )
                self._log(f"主页作品采集完成，共 {count} 条")

            self.progress_var.set(100)
            self.progress_label.config(text=f"完成! 共 {count} 条")

        except Exception as e:
            self._log(f"采集异常: {e}")
            self.progress_label.config(text="采集失败")

        finally:
            # 恢复UI状态
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            if self.crawler:
                self.crawler.close()

    def _stop_crawl(self):
        """停止采集"""
        self.is_running = False
        if self.crawler:
            self.crawler.stop()
        self._log("用户停止采集")
        self.progress_label.config(text="已停止")

    def run(self):
        """运行应用"""
        self.root.mainloop()


def main():
    """程序入口"""
    app = CrawlerApp()
    app.run()


if __name__ == '__main__':
    main()