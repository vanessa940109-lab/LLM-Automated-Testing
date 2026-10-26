
# ============================================================
# GitHub Issues Fetcher
# LLM 驅動之自動化測試生成與執行系統
#
# 功能：
# 1. 連接 GitHub API
# 2. 取得 100 筆 GitHub Issues
# 3. 同時抓取 Open / Closed Issues
# 4. 自動排除 Pull Requests
# 5. 支援分頁與重複資料檢查
# 6. 整理 Issue 資料
# 7. 儲存成 github_issues.json
# 8. 使用 certifi 驗證 SSL 憑證
# ============================================================

import json
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error

from pathlib import Path

import certifi


# ============================================================
# 1. 基本設定
# ============================================================

# GitHub Repository
OWNER = "android"
REPO = "architecture-samples"

# 要取得的 Issue 數量
ISSUE_LIMIT = 100

# Issue 狀態：open / closed / all
ISSUE_STATE = "all"

# 每頁最多 100 筆
PER_PAGE = 100

# 輸出檔案
OUTPUT_FILE = Path(__file__).resolve().parent / "github_issues.json"

# GitHub API
API_BASE_URL = "https://api.github.com"

# 連線逾時秒數
REQUEST_TIMEOUT = 30

# 每頁請求之間的等待秒數
REQUEST_DELAY = 1


# ============================================================
# 2. 建立安全的 SSL 連線
# ============================================================

def create_ssl_context():

    # 使用 certifi 提供的 CA 憑證
    context = ssl.create_default_context(
        cafile=certifi.where()
    )

    return context


# ============================================================
# 3. 建立 GitHub API Request
# ============================================================

def create_request(page=1):

    # GitHub API 查詢參數
    params = urllib.parse.urlencode({
        "state": ISSUE_STATE,
        "per_page": PER_PAGE,
        "page": page,
        "sort": "created",
        "direction": "desc"
    })

    url = (
        f"{API_BASE_URL}/repos/"
        f"{OWNER}/{REPO}/issues?{params}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "LLM-Web-Test-System",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        method="GET"
    )

    return request


# ============================================================
# 4. 整理單筆 GitHub Issue
# ============================================================

def normalize_issue(item):

    issue = {
        "id": f"GH-{item['number']}",

        "number": item["number"],

        "title": item.get("title", ""),

        "description": item.get("body") or "",

        "labels": [
            label.get("name", "")
            for label in item.get("labels", [])
        ],

        "state": item.get("state", ""),

        "url": item.get("html_url", ""),

        "repository": f"{OWNER}/{REPO}",

        # 新增：建立時間
        "created_at": item.get("created_at", ""),

        # 新增：最後更新時間
        "updated_at": item.get("updated_at", ""),

        # 新增：關閉時間
        "closed_at": item.get("closed_at"),

        # 新增：留言數量
        "comments": item.get("comments", 0)
    }

    return issue


# ============================================================
# 5. 從 GitHub 讀取 Issues
# ============================================================

def fetch_github_issues():

    print()
    print("開始讀取 GitHub Issues...")
    print(f"Repository：{OWNER}/{REPO}")
    print(f"Issue State：{ISSUE_STATE}")
    print(f"目標數量：{ISSUE_LIMIT}")

    ssl_context = create_ssl_context()

    issues = []

    # 使用 set 避免重複 Issue
    seen_numbers = set()

    page = 1

    while len(issues) < ISSUE_LIMIT:

        request = create_request(page)

        print()
        print(f"正在讀取第 {page} 頁...")

        try:

            with urllib.request.urlopen(
                request,
                timeout=REQUEST_TIMEOUT,
                context=ssl_context
            ) as response:

                data = json.load(response)

        except urllib.error.HTTPError as error:

            detail = error.read().decode(
                "utf-8",
                errors="replace"
            )

            if error.code == 403:
                raise RuntimeError(
                    "GitHub API 拒絕請求，可能已達速率限制。"
                    f"詳細資訊：{detail[:300]}"
                ) from error

            raise RuntimeError(
                f"GitHub API HTTP {error.code}: "
                f"{detail[:300]}"
            ) from error

        except urllib.error.URLError as error:

            raise RuntimeError(
                f"GitHub 連線失敗：{error.reason}"
            ) from error

        except ssl.SSLError as error:

            raise RuntimeError(
                f"SSL 憑證驗證失敗：{error}"
            ) from error

        # 確認 API 回傳的是陣列
        if not isinstance(data, list):

            raise RuntimeError(
                "GitHub API 回傳格式不是 Issue 陣列"
            )

        # 沒有更多資料
        if not data:

            print("沒有更多 Issues")
            break

        for item in data:

            # 排除 Pull Requests
            if "pull_request" in item:
                continue

            issue_number = item["number"]

            # 排除重複 Issue
            if issue_number in seen_numbers:
                continue

            seen_numbers.add(issue_number)

            issue = normalize_issue(item)

            issues.append(issue)

            if len(issues) >= ISSUE_LIMIT:
                break

        print(
            f"目前累積取得 {len(issues)} 筆 Issues"
        )

        # 如果不足一頁，代表已到最後一頁
        if len(data) < PER_PAGE:
            print("已到達最後一頁")
            break

        # 下一頁
        page += 1

        # 避免連續發送過多請求
        if len(issues) < ISSUE_LIMIT:
            time.sleep(REQUEST_DELAY)

    return issues


# ============================================================
# 6. 儲存 GitHub Issues
# ============================================================

def save_issues(issues):

    # 避免沒有資料時覆蓋舊檔案
    if not issues:

        print()
        print("沒有取得 Issues，不覆蓋原本檔案")
        return

    # 先寫入暫存檔，成功後再取代原檔
    temp_file = OUTPUT_FILE.with_suffix(".json.tmp")

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                issues,
                file,
                ensure_ascii=False,
                indent=4
            )

        temp_file.replace(OUTPUT_FILE)

    finally:

        if temp_file.exists():
            temp_file.unlink()

    print()
    print(f"資料已儲存：{OUTPUT_FILE}")


# ============================================================
# 7. 顯示 Issues
# ============================================================

def print_issues(issues):

    print()
    print("=" * 60)
    print("GitHub Issues 讀取結果")
    print("=" * 60)

    for index, issue in enumerate(
        issues,
        start=1
    ):

        print()
        print(f"[{index}] {issue['id']}")
        print(f"Title：{issue['title']}")
        print(f"State：{issue['state']}")
        print(f"Labels：{issue['labels']}")
        print(f"URL：{issue['url']}")

        description = issue["description"]

        if description:

            preview = description[:150].replace(
                "\n", " "
            )

            print(f"Description：{preview}...")

        else:

            print("Description：無描述")


# ============================================================
# 8. 統計 Issues
# ============================================================

def print_statistics(issues):

    total = len(issues)

    open_count = sum(
        1 for issue in issues
        if issue["state"] == "open"
    )

    closed_count = sum(
        1 for issue in issues
        if issue["state"] == "closed"
    )

    with_description = sum(
        1 for issue in issues
        if issue["description"].strip()
    )

    without_description = total - with_description

    print()
    print("=" * 60)
    print("GitHub Issues 統計結果")
    print("=" * 60)

    print(f"總 Issue 數量：{total}")
    print(f"Open Issues：{open_count}")
    print(f"Closed Issues：{closed_count}")
    print(f"有描述 Issues：{with_description}")
    print(f"無描述 Issues：{without_description}")

    print("=" * 60)


# ============================================================
# 9. 主程式
# ============================================================

def main():

    print()
    print("=" * 60)
    print("GitHub Issues Fetcher")
    print("=" * 60)

    try:

        issues = fetch_github_issues()

        print_issues(issues)

        print_statistics(issues)

        save_issues(issues)

    except Exception as error:

        print()
        print("=" * 60)
        print("GitHub Issues 處理失敗")
        print("=" * 60)

        print(f"錯誤原因：{error}")

        print()
        print("請檢查：")
        print("1. 電腦是否可以連上 GitHub")
        print("2. 是否已安裝 certifi")
        print("3. GitHub API 是否達到速率限制")
        print("4. SSL 憑證是否受到網路環境影響")

        return

    print()
    print("=" * 60)
    print("GitHub Issues Fetcher Summary")
    print("=" * 60)

    print(f"Repository：{OWNER}/{REPO}")
    print(f"成功取得：{len(issues)} 筆 Issues")

    if issues:
        print(f"輸出檔案：{OUTPUT_FILE}")

    print("=" * 60)


if __name__ == "__main__":
    main()
