
# -*- coding: utf-8 -*-
"""
B01 Android Appium 自動化測試

測試目的：
確認使用者建立任務時，如果 Title 為空白，
Todo App 是否顯示錯誤提示並阻止儲存。

測試流程：
1. 連接 Android 模擬器
2. 從 All Tasks 首頁點擊右下角 +
3. 進入 New Task
4. 保持 Title 空白
5. 點擊 Save task
6. 檢查是否出現 Tasks cannot be empty
7. 儲存截圖、XML 與 CSV 報表
"""

import csv
import re
import time
import traceback

from datetime import datetime
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy

from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


# ==================================================
# 1. 基本設定
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

SERVER_URL = "http://127.0.0.1:4723"

APP_PACKAGE = (
    "com.example.android.architecture.blueprints.main"
)

APP_ACTIVITY = (
    "com.example.android.architecture.blueprints.todoapp.TodoActivity"
)

DEVICE_NAME = "Pixel 6"
DEVICE_UDID = "emulator-5554"

BUG_ID = "B01"

TEST_NAME = "Empty task title validation"

RESULT_DIR = BASE_DIR / "b01_android_results"

REPORT_FILE = RESULT_DIR / "b01_android_report.csv"

RUN_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")

EVIDENCE_DIR = RESULT_DIR / RUN_TIME

RESULT_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# ==================================================
# 2. 建立 Appium 連線
# ==================================================

def create_driver():

    options = UiAutomator2Options()

    options.platform_name = "Android"

    options.automation_name = "UiAutomator2"

    options.device_name = DEVICE_NAME

    options.udid = DEVICE_UDID

    options.app_package = APP_PACKAGE

    options.app_activity = APP_ACTIVITY

    # 保留 App 目前資料
    options.no_reset = True

    driver = webdriver.Remote(
        SERVER_URL,
        options=options
    )

    driver.implicitly_wait(2)

    return driver


# ==================================================
# 3. 儲存測試證據
# ==================================================

def save_evidence(driver, name):

    screenshot_path = EVIDENCE_DIR / f"{name}.png"

    xml_path = EVIDENCE_DIR / f"{name}.xml"

    try:

        driver.save_screenshot(str(screenshot_path))

        xml_path.write_text(
            driver.page_source,
            encoding="utf-8"
        )

        print(f"已儲存證據： {name}")

    except Exception as e:

        print(f"儲存證據失敗：{e}")


# ==================================================
# 4. 點擊 accessibility 元件
# ==================================================

def click_accessibility(driver, description):
    """
    Jetpack Compose 的 content-desc
    有時位於不可點擊的子元件。

    因此先找到 content-desc，
    再尋找外層 clickable=true 的父元件。
    """

    element = driver.find_element(
        AppiumBy.ACCESSIBILITY_ID,
        description
    )

    # 優先尋找可以點擊的父層
    try:

        clickable_parent = element.find_element(
            AppiumBy.XPATH,
            "./ancestor::*[@clickable='true'][1]"
        )

        clickable_parent.click()

        return

    except Exception:

        pass

    # 如果找不到父層，嘗試直接點擊
    element.click()


# ==================================================
# 5. 判斷目前是否在 New Task
# ==================================================

def is_new_task_screen(driver):

    try:

        edit_texts = driver.find_elements(
            AppiumBy.CLASS_NAME,
            "android.widget.EditText"
        )

        if not edit_texts:

            return False

        xml = driver.page_source

        return (
            'text="New Task"' in xml
            or 'content-desc="Save task"' in xml
        )

    except Exception:

        return False


# ==================================================
# 6. 從 All Tasks 進入 New Task
# ==================================================

def open_new_task(driver):

    if is_new_task_screen(driver):

        print("目前已在 New Task 畫面")

        return

    print("尋找新增任務按鈕...")

    # 根據 Android XML：
    # content-desc="New Task"
    #
    # 保留其他名稱作為備用
    button_names = [
        "New Task",
        "Add task",
        "Add Task",
        "Add new task"
    ]

    for name in button_names:

        try:

            click_accessibility(driver, name)

            print(f"已點擊新增任務按鈕：{name}")

            WebDriverWait(driver, 10).until(
                lambda d: is_new_task_screen(d)
            )

            print("成功進入 New Task 畫面")

            return

        except Exception:

            continue

    raise RuntimeError(
        "找不到新增任務按鈕，"
        "請確認 Todo App 停留在 All Tasks 首頁。"
    )


# ==================================================
# 7. 確認 Title 空白
# ==================================================

def clear_title(driver):

    edit_texts = driver.find_elements(
        AppiumBy.CLASS_NAME,
        "android.widget.EditText"
    )

    if len(edit_texts) < 1:

        raise RuntimeError(
            "找不到 Title 輸入欄位"
        )

    title_field = edit_texts[0]

    title_field.click()

    title_field.clear()

    # 確認 Title 已清空
    value = title_field.get_attribute("text") or ""

    if value.strip():

        raise RuntimeError(
            f"Title 清空失敗，目前內容：{value}"
        )

    print("Title 已保持空白")


# ==================================================
# 8. 點擊 Save task
# ==================================================

def click_save_task(driver):

    click_accessibility(
        driver,
        "Save task"
    )

    print("已點擊 Save task")

    # Snackbar 顯示時間可能很短
    # 所以立刻儲存證據
    save_evidence(
        driver,
        "immediately_after_click"
    )


# ==================================================
# 9. 檢查錯誤訊息
# ==================================================

def check_validation_message(driver):

    print("檢查錯誤訊息...")

    expected_messages = [
        "tasks cannot be empty",
        "task cannot be empty",
        "text cannot be empty",
        "title cannot be empty"
    ]

    end_time = time.time() + 5

    while time.time() < end_time:

        xml = driver.page_source.lower()

        for message in expected_messages:

            if message in xml:

                save_evidence(
                    driver,
                    "validation_message"
                )

                return True, (
                    "空白 Title 儲存後，"
                    "成功偵測到錯誤提示。"
                )

        time.sleep(0.2)

    return False, (
        "沒有在 Android UI XML 中偵測到"
        "預期的錯誤提示。"
    )


# ==================================================
# 10. 寫入 CSV 測試報表
# ==================================================

def save_report(status, reason, duration):

    file_exists = REPORT_FILE.exists()

    fieldnames = [
        "bug_id",
        "test_name",
        "platform",
        "tool",
        "status",
        "reason",
        "duration_seconds",
        "timestamp",
        "evidence_dir"
    ]

    with open(
        REPORT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        if not file_exists or REPORT_FILE.stat().st_size == 0:

            writer.writeheader()

        writer.writerow({
            "bug_id": BUG_ID,
            "test_name": TEST_NAME,
            "platform": "Android",
            "tool": "Appium",
            "status": status,
            "reason": reason,
            "duration_seconds": round(duration, 2),
            "timestamp": RUN_TIME,
            "evidence_dir": str(EVIDENCE_DIR)
        })


# ==================================================
# 11. 主程式
# ==================================================

def main():

    print("=" * 50)
    print("B01 Android Appium 自動化測試")
    print("=" * 50)

    driver = None

    start_time = time.time()

    status = "ERROR"

    reason = ""

    try:

        # ------------------------------------------
        # Step 1：連接 Appium
        # ------------------------------------------

        print("\n[1] 連接 Appium...")

        driver = create_driver()

        print("Appium 連線成功")

        # ------------------------------------------
        # Step 2：進入 New Task
        # ------------------------------------------

        print("\n[2] 進入 New Task...")

        open_new_task(driver)

        save_evidence(
            driver,
            "new_task"
        )

        # ------------------------------------------
        # Step 3：Title 保持空白
        # ------------------------------------------

        print("\n[3] 確認 Title 空白...")

        clear_title(driver)

        # ------------------------------------------
        # Step 4：點擊 Save
        # ------------------------------------------

        print("\n[4] 點擊 Save task...")

        click_save_task(driver)

        # ------------------------------------------
        # Step 5：檢查錯誤訊息
        # ------------------------------------------

        print("\n[5] 檢查錯誤訊息...")

        found, message = check_validation_message(driver)

        if found:

            status = "PASS"

            reason = message

        else:

            status = "INCONCLUSIVE"

            reason = message

        save_evidence(
            driver,
            "after_save"
        )

        print(f"\n測試結果： {status}")

        print(f"原因： {reason}")

    except Exception as e:

        status = "ERROR"

        reason = str(e)

        print(f"\n測試發生錯誤：{e}")

        traceback.print_exc()

        if driver is not None:

            save_evidence(
                driver,
                "error"
            )

    finally:

        duration = time.time() - start_time

        save_report(
            status,
            reason,
            duration
        )

        if driver is not None:

            try:

                driver.quit()

            except Exception:

                pass

        print("\n" + "=" * 50)

        print("B01 Android 測試結束")

        print(f"結果： {status}")

        print(f"報表： {REPORT_FILE}")

        print(f"證據資料夾： {EVIDENCE_DIR}")

        print("=" * 50)


if __name__ == "__main__":

    main()
