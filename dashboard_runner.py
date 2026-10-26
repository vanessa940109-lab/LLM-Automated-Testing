
# -*- coding: utf-8 -*-

# ============================================================
# Dashboard Selenium Runner
# LLM 自動化測試專題
#
# 功能：
# 1. 支援 B01 ~ B30
# 2. 自動切換 NORMAL / BUG MODE
# 3. 使用 Selenium 執行 JSON Test Plan
# 4. 自動產生 CSV 實驗紀錄
# 5. 記錄 run_id、時間、模型與測試結果
# 6. 保留 Dashboard / Batch Runner 呼叫介面
# ============================================================

import csv
import json
import uuid

from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from selenium import webdriver

from llm_planner import load_bug_cases
from llm_executor import run_case


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BASE_URL = "http://127.0.0.1:5000"

RESULT_DIR = BASE_DIR / "dashboard_results"

PLAN_DIR = BASE_DIR / "generated_plans"

VALID_BUG_IDS = {
    f"B{i:02d}" for i in range(1, 31)
}

CSV_FIELDS = [
    "run_id",
    "timestamp",
    "bug_id",
    "category",
    "model",
    "mode",
    "plan_valid",
    "test_result",
    "duration_seconds",
    "error_message"
]


# ============================================================
# 2. 查詢目前 Todo Web 模式
# ============================================================

def get_web_mode():

    url = BASE_URL + "/test/mode"

    try:

        with urlopen(
            url,
            timeout=10
        ) as response:

            mode_info = json.load(response)

    except Exception as error:

        raise RuntimeError(
            "無法連線 Todo Web Application。"
            "請確認 app.py 已啟動。"
            f"詳細原因：{error}"
        ) from error

    return str(
        mode_info.get("mode", "")
    ).strip().lower()


# ============================================================
# 3. 切換 Todo Web 測試模式
# ============================================================

def set_web_mode(mode):

    mode = str(mode).strip().lower()

    if mode not in ("normal", "bug"):

        raise ValueError(
            f"不支援的測試模式：{mode}"
        )

    url = BASE_URL + "/test/mode"

    data = json.dumps({
        "mode": mode
    }).encode("utf-8")

    request = Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urlopen(
            request,
            timeout=10
        ) as response:

            if response.status != 200:

                raise RuntimeError(
                    "模式切換失敗"
                )

            response.read()

    except Exception as error:

        raise RuntimeError(
            "無法切換 Todo Web 測試模式。"
            "請確認 app.py 已新增 "
            "POST /test/mode API。"
            f"詳細原因：{error}"
        ) from error

    actual_mode = get_web_mode()

    if actual_mode != mode:

        raise RuntimeError(
            "模式切換後驗證失敗！"
            f"要求：{mode.upper()}，"
            f"實際：{actual_mode.upper()}"
        )

    return actual_mode


# ============================================================
# 4. 確認 Todo Web 模式
# ============================================================

def check_web_mode(mode):

    mode = str(mode).strip().lower()

    if mode not in ("normal", "bug"):

        raise ValueError(
            f"不支援的測試模式：{mode}"
        )

    actual_mode = get_web_mode()

    if actual_mode != mode:

        print(
            f"目前模式：{actual_mode.upper()}"
        )

        print(
            f"切換模式：{mode.upper()}"
        )

        actual_mode = set_web_mode(mode)

    return actual_mode


# ============================================================
# 5. 讀取 Bug Case
# ============================================================

def get_bug_case(bug_id):

    bugs = {
        bug["id"]: bug
        for bug in load_bug_cases()
    }

    if bug_id not in bugs:

        raise ValueError(
            f"bug_cases.json 找不到：{bug_id}"
        )

    return bugs[bug_id]


# ============================================================
# 6. 確認 JSON Test Plan
# ============================================================

def check_test_plan(bug_id):

    plan_file = (
        PLAN_DIR / f"{bug_id}.json"
    )

    if not plan_file.is_file():

        raise FileNotFoundError(
            f"找不到 {bug_id} 的 JSON Test Plan。"
        )

    try:

        with plan_file.open(
            "r",
            encoding="utf-8"
        ) as file:

            plan = json.load(file)

    except json.JSONDecodeError as error:

        raise ValueError(
            f"{bug_id} JSON 格式錯誤：{error}"
        ) from error

    if not isinstance(plan, dict):

        raise ValueError(
            f"{bug_id} Test Plan 必須是 JSON 物件"
        )

    if not isinstance(
        plan.get("steps"),
        list
    ):

        raise ValueError(
            f"{bug_id} Test Plan 缺少 steps 陣列"
        )

    return plan


# ============================================================
# 7. 取得模型來源
# ============================================================

def get_plan_model(plan):

    model = plan.get("model")

    if isinstance(model, str):

        model = model.strip()

        if model:
            return model

    return "unknown"


# ============================================================
# 8. 儲存 CSV
# ============================================================

def save_result_csv(record, bug_id, mode):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    file_timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    result_file = (
        RESULT_DIR
        / f"{bug_id}_{mode}_{file_timestamp}.csv"
    )

    with result_file.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS
        )

        writer.writeheader()
        writer.writerow(record)

    return result_file


# ============================================================
# 9. 執行指定測試案例
# ============================================================

def run_dashboard_test(bug_id, mode):

    bug_id = str(bug_id).strip().upper()
    mode = str(mode).strip().lower()

    # 驗證 Bug ID
    if bug_id not in VALID_BUG_IDS:

        raise ValueError(
            f"不支援的測試案例：{bug_id}"
        )

    # 驗證模式
    if mode not in ("normal", "bug"):

        raise ValueError(
            f"不支援的測試模式：{mode}"
        )

    # 確認並切換測試模式
    actual_mode = check_web_mode(mode)

    # 讀取測試案例
    bug = get_bug_case(bug_id)

    # 讀取 Test Plan
    plan = check_test_plan(bug_id)

    # 模型來源
    model = get_plan_model(plan)

    # 實驗識別碼
    run_id = uuid.uuid4().hex[:12]

    timestamp = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    print()
    print("=" * 55)
    print("Dashboard Selenium Test")
    print("=" * 55)

    print(f"Run ID：{run_id}")
    print(f"測試案例：{bug_id}")
    print(f"測試模式：{actual_mode.upper()}")
    print(f"模型來源：{model}")

    print("=" * 55)

    # Selenium 執行
    driver = None

    try:

        driver = webdriver.Chrome()

        result = run_case(
            driver,
            bug
        )

    finally:

        if driver is not None:
            driver.quit()

    # 整理實驗紀錄
    record = {
        "run_id": run_id,
        "timestamp": timestamp,
        "bug_id": bug_id,
        "category": result.get(
            "category", ""
        ),
        "model": model,
        "mode": mode.upper(),
        "plan_valid": result.get(
            "plan_valid", False
        ),
        "test_result": result.get(
            "test_result", "ERROR"
        ),
        "duration_seconds": result.get(
            "duration_seconds", 0
        ),
        "error_message": result.get(
            "error_message", ""
        )
    }

    # 儲存 CSV
    result_file = save_result_csv(
        record,
        bug_id,
        mode
    )

    print()
    print("=" * 55)
    print("Test Result")
    print("=" * 55)

    print(
        f"測試結果：{record['test_result']}"
    )

    print(
        f"執行時間："
        f"{record['duration_seconds']} 秒"
    )

    if record["error_message"]:

        print(
            f"錯誤訊息："
            f"{record['error_message']}"
        )

    print(
        f"CSV：{result_file}"
    )

    print("=" * 55)

    return {
        "run_id": run_id,
        "bug_id": bug_id,
        "mode": mode,
        "category": record["category"],
        "model": model,
        "plan_valid": record["plan_valid"],
        "test_result": record["test_result"],
        "duration_seconds": (
            record["duration_seconds"]
        ),
        "error_message": (
            record["error_message"]
        ),
        "result_file": str(
            result_file
        )
    }


# ============================================================
# 10. 單獨執行
# ============================================================

if __name__ == "__main__":

    print(
        "Dashboard Runner 已載入。"
    )

    print(
        "請透過 dashboard.py "
        "選擇測試案例並執行。"
    )
