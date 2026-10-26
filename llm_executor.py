
# -*- coding: utf-8 -*-

# ============================================================
# LLM Selenium Test Executor
# B01 ~ B30
#
# 功能：
# 1. 讀取並驗證 LLM JSON Test Plan
# 2. 使用 Selenium 執行 Todo Web 測試
# 3. 支援 NORMAL / BUG MODE
# 4. 判斷 PASS / BUG_REPRODUCED / ERROR
# 5. 每個案例執行前重設資料
# 6. 儲存 CSV 測試結果
# ============================================================

import csv
import json
import time

from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from llm_planner import (
    load_bug_cases,
    validate_bug_plan,
    get_case_config
)


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BASE_URL = "http://127.0.0.1:5000"

PLAN_DIR = BASE_DIR / "generated_plans"

RESULT_FILE = BASE_DIR / "test_results_all.csv"

VALID_BUG_IDS = [
    f"B{i:02d}" for i in range(1, 31)
]

WAIT_SECONDS = 10

BY = {
    "id": By.ID,
    "class": By.CLASS_NAME,
    "css": By.CSS_SELECTOR,
    "name": By.NAME
}

TASK_SCOPED = {
    "task-checkbox",
    "task-title",
    "edit-link",
    "delete-button"
}


# ============================================================
# 2. 重設測試資料
# ============================================================

def reset_data():

    request = Request(
        BASE_URL + "/test/reset",
        data=b"",
        method="POST"
    )

    with urlopen(request, timeout=10) as response:

        if response.status != 200:
            raise RuntimeError("無法重設測試資料")

        response.read()


# ============================================================
# 3. 建立額外測試任務
# B19 / B21 使用
# ============================================================

def create_seed(title):

    data = urlencode({
        "title": title
    }).encode("utf-8")

    request = Request(
        BASE_URL + "/add",
        data=data,
        method="POST"
    )

    with urlopen(request, timeout=10) as response:
        response.read()


# ============================================================
# 4. 讀取 JSON Test Plan
# ============================================================

def load_plan(bug_id):

    path = PLAN_DIR / f"{bug_id}.json"

    if not path.is_file():
        raise FileNotFoundError(
            f"找不到 Test Plan：{path}"
        )

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# 5. 任務查詢工具
# ============================================================

def task_rows(driver):

    return driver.find_elements(
        By.CLASS_NAME,
        "task"
    )


def raw_title(element):

    # 讀取 HTML 中的原始文字
    text = (
        element.get_attribute("textContent")
        or ""
    )

    # 移除模板產生的換行與縮排
    # 保留任務名稱真正的前後空白
    if "\n" in text or "\r" in text:

        lines = text.splitlines()

        if len(lines) >= 3:
            text = "".join(lines[1:-1])
        else:
            text = text.strip("\r\n")

        # 只移除模板固定縮排
        if text.startswith("    "):
            text = text[4:]

    return text


def normalized_title(element):

    return raw_title(element).strip()


def find_task_row(driver, title):

    expected = title.strip()

    for row in task_rows(driver):

        titles = row.find_elements(
            By.CLASS_NAME,
            "task-title"
        )

        for element in titles:

            if normalized_title(element) == expected:
                return row

    return None


def wait_for_task(driver, title):

    return WebDriverWait(
        driver,
        WAIT_SECONDS
    ).until(
        lambda d: find_task_row(d, title)
    )


def count_title(driver, title):

    expected = title.strip()

    count = 0

    for row in task_rows(driver):

        titles = row.find_elements(
            By.CLASS_NAME,
            "task-title"
        )

        for element in titles:

            if normalized_title(element) == expected:
                count += 1
                break

    return count


def count_exact_title(driver, title):

    # B14 專用：完整比對前後空白
    count = 0

    for row in task_rows(driver):

        titles = row.find_elements(
            By.CLASS_NAME,
            "task-title"
        )

        for element in titles:

            if raw_title(element) == title:
                count += 1
                break

    return count


def get_completed(driver, title):

    row = find_task_row(driver, title)

    if row is None:
        raise RuntimeError(
            f"找不到任務：{title!r}"
        )

    checkbox = row.find_element(
        By.CLASS_NAME,
        "task-checkbox"
    )

    return checkbox.is_selected()


# ============================================================
# 6. Selenium 元素定位
# ============================================================

def locate(driver, wait, step, context):

    target = step["target"]

    config = context["config"]

    locator_type = config["elements"].get(target)

    if locator_type not in BY:

        raise ValueError(
            f"不支援的定位："
            f"{target} / {locator_type}"
        )

    locator = (
        BY[locator_type],
        target
    )

    if target in TASK_SCOPED:

        title = (
            step.get("task")
            or context.get("current_title")
            or context.get("task_title")
        )

        if not title:

            raise RuntimeError(
                f"{target} 缺少任務名稱"
            )

        row = wait_for_task(
            driver,
            title
        )

        return row.find_element(
            *locator
        )

    return wait.until(
        EC.element_to_be_clickable(locator)
    )


# ============================================================
# 7. 執行 JSON Step
# ============================================================

def execute_step(driver, wait, step, context):

    action = step["action"]
    target = step["target"]

    print(
        f"執行 Step：{action} -> {target}"
    )

    if action == "open":

        if target != "/":
            raise ValueError(
                "open 只允許 /"
            )

        driver.get(
            BASE_URL + "/"
        )

        return

    element = locate(
        driver,
        wait,
        step,
        context
    )

    if action == "input":

        value = step["value"]

        element.clear()
        element.send_keys(value)

        if target == "title":

            context["task_title"] = value
            context["current_title"] = value

        elif target == "edit-title":

            context["edited_title"] = value

        return

    if action == "click":

        element.click()

        if target == "save-edit":

            context["current_title"] = (
                context.get(
                    "edited_title",
                    context.get("current_title")
                )
            )

        return

    if action == "check":

        if not element.is_selected():
            element.click()

        return

    if action == "uncheck":

        if element.is_selected():
            element.click()

        return

    raise ValueError(
        f"不支援的 action：{action}"
    )


# ============================================================
# 8. B28 詳細頁狀態
# ============================================================

def detail_status(driver):

    status_element = driver.find_element(
        By.ID,
        "task-status"
    )

    status_text = (
        status_element.text
        .strip()
        .lower()
    )

    print(
        f"B28 詳細頁狀態：{status_text}"
    )

    if "active" in status_text:
        return False

    if "completed" in status_text:
        return True

    raise RuntimeError(
        f"B28 無法辨識詳細頁狀態：{status_text}"
    )


# ============================================================
# 9. 測試結果判斷
# ============================================================

def evaluate(driver, bug_id, context):

    title = context.get(
        "task_title", ""
    )

    edited = context.get(
        "edited_title", ""
    )

    # 保留當前畫面的案例
    keep_current_page = {
        "B05",
        "B06",
        "B09",
        "B23",
        "B24",
        "B25",
        "B27",
        "B28"
    }

    if bug_id not in keep_current_page:

        driver.get(
            BASE_URL + "/"
        )

    # B01：空白任務
    if bug_id == "B01":

        return (
            "BUG_REPRODUCED"
            if len(task_rows(driver)) > 0
            else "PASS"
        )

    # B02：編輯未儲存
    if bug_id == "B02":

        if (
            count_title(driver, edited) == 1
            and count_title(driver, title) == 0
        ):
            return "PASS"

        if count_title(driver, title) == 1:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B03 / B08 / B20：刪除失敗
    if bug_id in ("B03", "B08", "B20"):

        return (
            "BUG_REPRODUCED"
            if count_title(driver, title) > 0
            else "PASS"
        )

    # B04：無法完成
    if bug_id == "B04":

        return (
            "PASS"
            if get_completed(driver, title)
            else "BUG_REPRODUCED"
        )

    # B05 / B06：篩選異常
    if bug_id in ("B05", "B06"):

        expected_completed = (
            bug_id == "B06"
        )

        if (
            context.get(
                "before_filter_completed"
            ) != expected_completed
        ):

            raise RuntimeError(
                f"{bug_id} 篩選前狀態不符"
            )

        return (
            "PASS"
            if count_title(driver, title) == 1
            else "BUG_REPRODUCED"
        )

    # B07：取消完成失敗
    if bug_id == "B07":

        return (
            "BUG_REPRODUCED"
            if get_completed(driver, title)
            else "PASS"
        )

    # B09：詳細頁名稱錯誤
    if bug_id == "B09":

        actual = driver.find_element(
            By.ID,
            "task-title"
        ).get_attribute("textContent") or ""

        return (
            "PASS"
            if actual.strip() == title
            else "BUG_REPRODUCED"
        )

    # B10：HTTP 500
    if bug_id == "B10":

        if context.get("server_error"):
            return "BUG_REPRODUCED"

        return (
            "PASS"
            if count_title(driver, title) == 1
            else "ERROR"
        )

    # B11：重複任務
    if bug_id == "B11":

        count = count_title(driver, title)

        if count > 1:
            return "BUG_REPRODUCED"

        if count == 1:
            return "PASS"

        return "ERROR"

    # B12 / B13 / B30：任務名稱被修改
    if bug_id in ("B12", "B13", "B30"):

        if count_title(driver, title) == 1:
            return "PASS"

        if len(task_rows(driver)) > 0:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B14：前後空白遭刪除
    if bug_id == "B14":

        if count_exact_title(driver, title) == 1:
            return "PASS"

        if count_title(driver, title) == 1:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B15：編輯後重複任務
    if bug_id == "B15":

        if (
            len(task_rows(driver)) == 1
            and count_title(driver, edited) == 1
        ):
            return "PASS"

        return "BUG_REPRODUCED"

    # B16：編輯特殊字元遺失
    if bug_id == "B16":

        if count_title(driver, edited) == 1:
            return "PASS"

        if len(task_rows(driver)) > 0:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B17：錯誤接受空白編輯
    if bug_id == "B17":

        if count_title(driver, title) == 1:
            return "PASS"

        if len(task_rows(driver)) > 0:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B18：編輯後完成狀態重設
    if bug_id == "B18":

        return (
            "PASS"
            if get_completed(driver, edited)
            else "BUG_REPRODUCED"
        )

    # B19：刪除錯誤任務
    if bug_id == "B19":

        original_count = count_title(
            driver,
            title
        )

        other_count = count_title(
            driver,
            context["seed_title"]
        )

        if (
            original_count == 0
            and other_count == 1
        ):
            return "PASS"

        if (
            original_count == 1
            and other_count == 0
        ):
            return "BUG_REPRODUCED"

        return "ERROR"

    # B21：其他任務狀態被修改
    if bug_id == "B21":

        if not get_completed(
            driver,
            title
        ):
            return "ERROR"

        if get_completed(
            driver,
            context["seed_title"]
        ):
            return "BUG_REPRODUCED"

        return "PASS"

    # B22：取消完成時名稱被修改
    if bug_id == "B22":

        if (
            count_title(driver, title) == 1
            and not get_completed(driver, title)
        ):
            return "PASS"

        if len(task_rows(driver)) > 0:
            return "BUG_REPRODUCED"

        return "ERROR"

    # B23 / B24：篩選顯示錯誤
    if bug_id in ("B23", "B24"):

        return (
            "BUG_REPRODUCED"
            if count_title(driver, title) > 0
            else "PASS"
        )

    # B25：All 篩選隱藏任務
    if bug_id == "B25":

        return (
            "PASS"
            if count_title(driver, title) == 1
            else "BUG_REPRODUCED"
        )

    # B26：篩選改變完成狀態
    if bug_id == "B26":

        return (
            "BUG_REPRODUCED"
            if get_completed(driver, title)
            else "PASS"
        )

    # B27：重新整理後任務消失
    if bug_id == "B27":

        if not context.get(
            "before_refresh_exists"
        ):
            return "ERROR"

        return (
            "BUG_REPRODUCED"
            if count_title(driver, title) == 0
            else "PASS"
        )

    # B28：詳細頁狀態錯誤
    if bug_id == "B28":

        before = context.get(
            "before_detail_completed"
        )

        if before is None:
            return "ERROR"

        return (
            "PASS"
            if detail_status(driver) == before
            else "BUG_REPRODUCED"
        )

    # B29：清除未完成任務
    if bug_id == "B29":

        return (
            "PASS"
            if count_title(driver, title) == 1
            else "BUG_REPRODUCED"
        )

    raise ValueError(
        f"沒有 {bug_id} 的 Evaluator"
    )


# ============================================================
# 10. 執行單一案例
# ============================================================

def run_case(driver, bug):

    bug_id = bug["id"]

    start = time.perf_counter()

    result = {
        "bug_id": bug_id,
        "category": "",
        "plan_valid": False,
        "test_result": "ERROR",
        "duration_seconds": 0,
        "error_message": ""
    }

    try:

        plan = load_plan(bug_id)

        result["category"] = plan.get(
            "category", ""
        )

        valid, reason = validate_bug_plan(
            bug,
            plan
        )

        if not valid:

            result["test_result"] = "PLAN_INVALID"
            result["error_message"] = reason

            return result

        result["plan_valid"] = True

        print("PLAN_VALID")

        reset_data()

        context = {
            "config": get_case_config(bug),
            "task_title": "",
            "current_title": ""
        }

        # B19 / B21：建立第二筆任務
        if bug_id in ("B19", "B21"):

            context["seed_title"] = (
                f"{bug_id}_OTHER_TASK"
            )

            create_seed(
                context["seed_title"]
            )

        driver.get(
            BASE_URL + "/"
        )

        wait = WebDriverWait(
            driver,
            WAIT_SECONDS
        )

        steps = plan["steps"]

        for index, step in enumerate(steps):

            action = step["action"]
            target = step["target"]

            print(
                f"{bug_id} Step "
                f"{index + 1}/{len(steps)}："
                f"{action} {target}"
            )

            # B05 / B06：篩選前狀態
            if (
                bug_id in ("B05", "B06")
                and action == "click"
                and target in (
                    "filter-active",
                    "filter-completed"
                )
            ):

                context[
                    "before_filter_completed"
                ] = get_completed(
                    driver,
                    context["task_title"]
                )

            # B28：詳細頁前狀態
            if (
                bug_id == "B28"
                and action == "click"
                and target == "task-title"
            ):

                context[
                    "before_detail_completed"
                ] = get_completed(
                    driver,
                    context["task_title"]
                )

            # B27：重新整理前確認任務
            if (
                bug_id == "B27"
                and action == "open"
                and index > 0
            ):

                context[
                    "before_refresh_exists"
                ] = (
                    count_title(
                        driver,
                        context["task_title"]
                    ) == 1
                )

            execute_step(
                driver,
                wait,
                step,
                context
            )

            # B10：檢查 HTTP 500
            if (
                bug_id == "B10"
                and action == "click"
                and target == "add-task"
            ):

                page = (
                    driver.title
                    + " "
                    + driver.page_source
                ).lower()

                context["server_error"] = any(
                    keyword in page
                    for keyword in (
                        "internal server error",
                        "werkzeug debugger",
                        "500 internal server error"
                    )
                )

            time.sleep(0.15)

        result["test_result"] = evaluate(
            driver,
            bug_id,
            context
        )

    except Exception as error:

        result["test_result"] = "ERROR"

        result["error_message"] = (
            str(error)[:500]
        )

        print(
            f"{bug_id} ERROR：{error}"
        )

    finally:

        result["duration_seconds"] = round(
            time.perf_counter() - start,
            2
        )

    return result


# ============================================================
# 11. 儲存 CSV
# ============================================================

def save_results(results):

    fields = [
        "bug_id",
        "category",
        "plan_valid",
        "test_result",
        "duration_seconds",
        "error_message"
    ]

    with RESULT_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)


# ============================================================
# 12. 主程式
# ============================================================

def main():

    bugs = {
        bug["id"]: bug
        for bug in load_bug_cases()
    }

    results = []

    driver = webdriver.Chrome()

    try:

        for bug_id in VALID_BUG_IDS:

            if bug_id not in bugs:

                print(
                    f"略過未定義案例：{bug_id}"
                )

                continue

            result = run_case(
                driver,
                bugs[bug_id]
            )

            results.append(result)

            print(
                f"{bug_id}："
                f"{result['test_result']}"
            )

    finally:

        driver.quit()

    save_results(results)

    print()
    print("=" * 60)
    print("B01 ~ B30 Test Summary")
    print("=" * 60)

    for result in results:

        print(
            f"{result['bug_id']}："
            f"{result['test_result']}"
        )

    print("=" * 60)
    print(f"CSV：{RESULT_FILE}")


if __name__ == "__main__":
    main()
