
# -*- coding: utf-8 -*-

# ============================================================
# LLM Automated Testing Dashboard
#
# 功能：
# 1. B01 ~ B30 本地 Bug Cases
# 2. Selenium 單次測試
# 3. Selenium 批次測試
# 4. 選擇 LLM 模型與測試模式
# 5. 檢查 JSON Test Plan
# 6. 顯示測試結果
# 7. GitHub Issues / Appium CSV 統計
# 8. 從 Dashboard 啟動 Appium 測試
# 9. 防止同時啟動多個 Appium 測試
# 10. 儲存 Appium 執行紀錄
# ============================================================

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for
)

from pathlib import Path
import json
import csv
import subprocess
import sys
import threading
from datetime import datetime

from dashboard_runner import run_dashboard_test
from dashboard_batch_runner import run_batch_test


# ============================================================
# 1. 基本設定
# ============================================================

dashboard = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

BUG_CASES_FILE = BASE_DIR / "bug_cases.json"

PLAN_DIR = BASE_DIR / "generated_plans"

GITHUB_RESULTS_FILE = (
    BASE_DIR
    / "dashboard_data"
    / "merged_test_results.csv"
)

LOG_DIR = (
    BASE_DIR
    / "dashboard_data"
    / "appium_logs"
)

LOG_DIR.mkdir(parents=True, exist_ok=True)

BUG_IDS = [
    f"B{i:02d}"
    for i in range(1, 31)
]

BATCH_SUPPORTED_IDS = BUG_IDS.copy()

MODELS = {
    "3b": "qwen2.5:3b",
    "7b": "qwen2.5:7b"
}

VALID_REPEAT_COUNTS = (1, 3, 5, 10)


# ============================================================
# 2. Appium 測試設定
# ============================================================

APPIUM_SCRIPTS = {
     "GH-1046": "test_gh1046_verify.py",
     "GH-1035": "test_gh1035.py",
     "GH-969": "test_gh969.py",
     "B01": "test_b01_android.py",
}

appium_process = None
appium_issue_id = None

appium_lock = threading.Lock()


def get_appium_running():

    global appium_process
    global appium_issue_id

    with appium_lock:

        if appium_process is None:
            return False, None

        if appium_process.poll() is None:
            return True, appium_issue_id

        appium_process = None
        appium_issue_id = None

        return False, None


# ============================================================
# 3. 讀取本地 Bug Cases
# ============================================================

def load_local_bug_cases():

    if not BUG_CASES_FILE.exists():
        return []

    try:

        with BUG_CASES_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if not isinstance(data, list):
            return []

        return [
            item
            for item in data
            if (
                isinstance(item, dict)
                and item.get("id") in BUG_IDS
            )
        ]

    except (OSError, json.JSONDecodeError):
        return []


# ============================================================
# 4. 讀取 GitHub Issues
# ============================================================

def load_github_issues():

    file_path = BASE_DIR / "github_issues.json"

    if not file_path.exists():
        return []

    try:

        with file_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            issues = json.load(file)

        if isinstance(issues, list):
            return issues

        return []

    except (OSError, json.JSONDecodeError):
        return []


# ============================================================
# 5. 檢查 Test Plan
# ============================================================

def plan_exists(bug_id):

    plan_file = PLAN_DIR / f"{bug_id}.json"

    return plan_file.is_file()


def missing_plans(bug_ids):

    return [
        bug_id
        for bug_id in bug_ids
        if not plan_exists(bug_id)
    ]


# ============================================================
# 6. Selenium 測試結果狀態
# ============================================================

def get_result_status(test_result):

    if not isinstance(test_result, dict):
        return "error"

    result = test_result.get(
        "test_result",
        ""
    )

    if result in (
        "PASS",
        "BUG_REPRODUCED"
    ):
        return "success"

    return "error"


# ============================================================
# 7. 讀取 GitHub / Appium CSV
# ============================================================

def load_github_test_results():

    print(
        "目前讀取的 CSV：",
        GITHUB_RESULTS_FILE,
        flush=True
    )

    if not GITHUB_RESULTS_FILE.is_file():
        return []

    try:

        with GITHUB_RESULTS_FILE.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            results = []

            for row in reader:

                issue_id = (
                    row.get("issue_id") or ""
                ).strip()

                if not issue_id:
                    continue

                clean_row = {
                    key: (value or "").strip()
                    for key, value in row.items()
                    if key is not None
                }

                results.append(clean_row)

            print(
                "CSV 讀取筆數：",
                len(results),
                flush=True
            )

            return results

    except (OSError, csv.Error) as error:

        print(
            "[GitHub CSV] 讀取失敗：",
            error,
            flush=True
        )

        return []


# ============================================================
# 8. GitHub / Appium 統計
# ============================================================

def get_github_test_stats(results):

    reproduced = sum(
        row.get("status") == "BUG_REPRODUCED"
        for row in results
    )

    not_reproduced = sum(
        row.get("status") == "NOT_REPRODUCED"
        for row in results
    )

    suspected = sum(
        str(
            row.get("status", "")
        ).startswith("SUSPECTED_")
        for row in results
    )

    other = len(results) - (
        reproduced
        + not_reproduced
        + suspected
    )

    return {
        "total": len(results),
        "reproduced": reproduced,
        "not_reproduced": not_reproduced,
        "suspected": suspected,
        "other": other
    }


# ============================================================
# 9. Dashboard 首頁
# ============================================================

@dashboard.route("/", methods=["GET", "POST"])
def index():

    source = "local"
    model = "3b"
    bug_id = "B01"
    mode = "normal"

    test_type = "single"
    batch_range = "all"
    repeat_count = 1

    message = request.args.get("message", "")
    status = request.args.get("status", "")

    test_result = None

    local_bugs = load_local_bug_cases()

    available_ids = {
        item["id"]
        for item in local_bugs
    }

    # ========================================================
    # POST：處理原本的 Selenium 測試
    # ========================================================

    if request.method == "POST":

        source = request.form.get(
            "source",
            "local"
        )

        model = request.form.get(
            "model",
            "3b"
        )

        bug_id = request.form.get(
            "bug_id",
            "B01"
        )

        mode = request.form.get(
            "mode",
            "normal"
        )

        test_type = request.form.get(
            "test_type",
            "single"
        )

        batch_range = request.form.get(
            "batch_range",
            "all"
        )

        repeat_text = request.form.get(
            "repeat_count",
            "1"
        )

        # ----------------------------------------------------
        # 驗證設定
        # ----------------------------------------------------

        if source not in ("github", "local"):

            message = "不支援的測試來源"
            status = "error"

        elif model not in MODELS:

            message = "不支援的 LLM 模型"
            status = "error"

        elif mode not in ("bug", "normal"):

            message = "不支援的測試模式"
            status = "error"

        elif test_type not in ("single", "batch"):

            message = "不支援的執行方式"
            status = "error"

        # ----------------------------------------------------
        # GitHub 測試使用獨立路由
        # ----------------------------------------------------

        elif source == "github":

            message = (
                "GitHub / Appium 測試請使用"
                "下方的 Appium 執行功能。"
            )

            status = "error"

        elif model != "3b":

            message = (
                "目前只支援既有的 "
                "qwen2.5:3b Test Plan。"
                "7B 模型尚未完成串接。"
            )

            status = "error"

        # ----------------------------------------------------
        # Selenium 單次測試
        # ----------------------------------------------------

        elif test_type == "single":

            if bug_id not in BUG_IDS:

                message = "不支援的 Bug ID"
                status = "error"

            elif bug_id not in available_ids:

                message = (
                    f"{bug_id} 不存在於 "
                    "bug_cases.json"
                )

                status = "error"

            elif not plan_exists(bug_id):

                message = (
                    f"{bug_id} 尚未產生 JSON Test Plan。"
                    "請先執行 llm_planner.py。"
                )

                status = "error"

            else:

                try:

                    test_result = run_dashboard_test(
                        bug_id=bug_id,
                        mode=mode
                    )

                    result = test_result.get(
                        "test_result",
                        "ERROR"
                    )

                    message = (
                        f"{bug_id} 測試完成！"
                        f"結果：{result}"
                    )

                    error_message = test_result.get(
                        "error_message",
                        ""
                    )

                    if error_message:

                        message += (
                            f"；原因：{error_message}"
                        )

                    status = get_result_status(
                        test_result
                    )

                except Exception as error:

                    message = (
                        f"單次測試執行失敗：{error}"
                    )

                    status = "error"

        # ----------------------------------------------------
        # Selenium 批次測試
        # ----------------------------------------------------

        elif test_type == "batch":

            if batch_range != "all":

                message = "不支援的批次測試範圍"
                status = "error"

            elif (
                not repeat_text.isdigit()
                or int(repeat_text)
                not in VALID_REPEAT_COUNTS
            ):

                message = "不支援的重複次數"
                status = "error"

            else:

                repeat_count = int(repeat_text)

                missing_cases = [
                    case_id
                    for case_id in BATCH_SUPPORTED_IDS
                    if case_id not in available_ids
                ]

                missing = missing_plans(
                    BATCH_SUPPORTED_IDS
                )

                if missing_cases:

                    message = (
                        "以下案例不存在於 bug_cases.json："
                        + ", ".join(missing_cases)
                    )

                    status = "error"

                elif missing:

                    message = (
                        "以下案例缺少 JSON Test Plan："
                        + ", ".join(missing)
                        + "。請先執行 llm_planner.py。"
                    )

                    status = "error"

                else:

                    try:

                        test_result = run_batch_test(
                            mode=mode,
                            repeat_count=repeat_count
                        )

                        total = test_result.get(
                            "total_tests",
                            0
                        )

                        expected = test_result.get(
                            "expected_count",
                            0
                        )

                        rate = test_result.get(
                            "expected_rate",
                            0
                        )

                        message = (
                            "批次測試完成！"
                            "測試範圍：B01～B30。"
                            f"總測試次數：{total}，"
                            f"符合預期：{expected}，"
                            f"符合預期比例：{rate}%"
                        )

                        if (
                            total > 0
                            and expected == total
                        ):

                            status = "success"

                        else:

                            status = "error"

                    except Exception as error:

                        message = (
                            f"批次測試執行失敗：{error}"
                        )

                        status = "error"

    # ========================================================
    # 讀取 GitHub / Appium 結果
    # ========================================================

    issues = load_github_issues()

    github_test_results = (
        load_github_test_results()
    )

    github_test_stats = get_github_test_stats(
        github_test_results
    )

    running, running_issue = get_appium_running()

    # ========================================================
    # 顯示 Dashboard
    # ========================================================

    return render_template(
        "dashboard.html",

        source=source,
        model=model,
        bug_id=bug_id,
        mode=mode,

        test_type=test_type,
        batch_range=batch_range,
        repeat_count=repeat_count,

        message=message,
        status=status,

        bug_ids=BUG_IDS,
        local_bugs=local_bugs,
        issues=issues,

        test_result=test_result,

        total_bug_cases=len(local_bugs),

        generated_plan_count=sum(
            1
            for item in local_bugs
            if plan_exists(item["id"])
        ),

        batch_supported_count=len(
            BATCH_SUPPORTED_IDS
        ),

        github_test_results=github_test_results,
        github_test_stats=github_test_stats,

        appium_scripts=APPIUM_SCRIPTS,
        appium_running=running,
        appium_running_issue=running_issue
    )


# ============================================================
# 10. 從 Dashboard 啟動 Appium 測試
# ============================================================

@dashboard.route(
    "/run-appium",
    methods=["POST"]
)
def run_appium_test():

    global appium_process
    global appium_issue_id

    issue_id = request.form.get(
        "issue_id",
        ""
    )

    # --------------------------------------------------------
    # 檢查 Issue
    # --------------------------------------------------------

    if issue_id not in APPIUM_SCRIPTS:

        return redirect(
            url_for(
                "index",
                message="不支援的 GitHub Issue",
                status="error"
            )
        )

    script_name = APPIUM_SCRIPTS[issue_id]

    script_path = BASE_DIR / script_name

    if not script_path.is_file():

        return redirect(
            url_for(
                "index",
                message=f"找不到測試檔案：{script_name}",
                status="error"
            )
        )

    # --------------------------------------------------------
    # 檢查是否已有 Appium 測試執行中
    # --------------------------------------------------------

    with appium_lock:

        if (
            appium_process is not None
            and appium_process.poll() is None
        ):

            return redirect(
                url_for(
                    "index",
                    message=(
                        f"{appium_issue_id} 正在測試中，"
                        "請等待完成。"
                    ),
                    status="error"
                )
            )

        # ----------------------------------------------------
        # 建立執行紀錄
        # ----------------------------------------------------

        run_time = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        log_file = (
            LOG_DIR
            / f"{issue_id}_{run_time}.log"
        )

        try:

            with log_file.open(
                "w",
                encoding="utf-8"
            ) as log:

                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(script_path)
                    ],
                    cwd=str(BASE_DIR),
                    stdout=log,
                    stderr=subprocess.STDOUT
                )

            appium_process = process
            appium_issue_id = issue_id

            print(
                "[Dashboard] Appium 已啟動：",
                issue_id,
                "PID：",
                process.pid,
                flush=True
            )

        except Exception as error:

            return redirect(
                url_for(
                    "index",
                    message=f"Appium 啟動失敗：{error}",
                    status="error"
                )
            )

    return redirect(
        url_for(
            "index",
            message=(
                f"{issue_id} Appium 測試已啟動。"
                "請稍後查看結果。"
            ),
            status="success"
        )
    )


# ============================================================
# 11. 啟動 Dashboard
# ============================================================

if __name__ == "__main__":

    print("=" * 55)
    print("LLM Automated Testing Dashboard")
    print("=" * 55)

    print("本地 Bug Cases：B01 ~ B30")
    print("批次 Runner：B01 ~ B30")

    print(
        "GitHub / Appium CSV：",
        GITHUB_RESULTS_FILE
    )

    print(
        "Dashboard URL："
        "http://127.0.0.1:5001"
    )

    print("=" * 55)

    dashboard.run(
        host="127.0.0.1",
        port=5001,
        debug=False,
        use_reloader=False
    )
