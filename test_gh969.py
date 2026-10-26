
# ================================================
# GH-969 Android UI 自動化驗證 V2
# Pixel 6 + Appium + UiAutomator2
#
# 測試內容：
# 1. 確認 Task List
# 2. 將任務設定為未完成
# 3. 勾選任務
# 4. 取消勾選任務
# 5. 記錄 Checkbox 狀態
# 6. 記錄 Snackbar
# 7. 進入 Task Details 比較狀態
# 8. 儲存 CSV、XML、截圖
# 9. 自動更新 Dashboard
#
# 不新增、不刪除任務
# ================================================

import csv
import time
import subprocess
import sys

from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


# ================================================
# 基本設定
# ================================================

SERVER_URL = "http://127.0.0.1:4723"

APP_PACKAGE = (
    "com.example.android.architecture.blueprints.main"
)

APP_ACTIVITY = (
    "com.example.android.architecture.blueprints.todoapp.TodoActivity"
)

TASK_TITLE = "GH1046_Test_142710"

BASE_DIR = Path(__file__).resolve().parent

RESULT_DIR = BASE_DIR / "gh969_results"

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

RUN_DIR = RESULT_DIR / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

REPORT_FILE = RESULT_DIR / "gh969_v2_report.csv"


# ================================================
# 自訂例外：發現疑似 App 異常
# ================================================

class SuspectedAppBug(Exception):
    pass


# ================================================
# 等待指定文字
# ================================================

def wait_text(driver, text, timeout=15):

    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_elements(
            AppiumBy.XPATH,
            f'//*[@text="{text}"]'
        )[0] if d.find_elements(
            AppiumBy.XPATH,
            f'//*[@text="{text}"]'
        ) else False
    )


# ================================================
# 尋找指定任務的 Checkbox
# ================================================

def find_task_checkbox(driver):

    xpath = (
        f'//*[@text="{TASK_TITLE}"]'
        '/parent::android.view.View'
        '/android.widget.CheckBox'
    )

    elements = driver.find_elements(
        AppiumBy.XPATH,
        xpath
    )

    if not elements:
        raise RuntimeError(
            f"找不到任務 {TASK_TITLE} 對應的 Checkbox"
        )

    return elements[0]


# ================================================
# 讀取 Checkbox 狀態
# ================================================

def checkbox_state(driver):

    checkbox = find_task_checkbox(driver)

    value = checkbox.get_attribute("checked")

    state = str(value).lower() == "true"

    print(
        "[DEBUG] 任務：",
        TASK_TITLE,
        "checked：",
        state
    )

    return state


# ================================================
# 等待 Checkbox 切換狀態
# ================================================

def wait_checkbox_state(driver, expected, timeout=6):

    try:

        WebDriverWait(
            driver,
            timeout,
            poll_frequency=0.5
        ).until(
            lambda d: checkbox_state(d) == expected
        )

        return True

    except TimeoutException:

        return False


# ================================================
# 儲存截圖與 XML
# ================================================

def save_evidence(driver, name):

    screenshot = RUN_DIR / f"{name}.png"
    xml_file = RUN_DIR / f"{name}.xml"

    driver.save_screenshot(str(screenshot))

    xml_text = driver.page_source

    xml_file.write_text(
        xml_text,
        encoding="utf-8"
    )

    print("已儲存：", name)

    return xml_text


# ================================================
# 從 XML 尋找 Snackbar
# ================================================

def find_snackbar(xml_text):

    messages = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return messages

    for element in root.iter():

        attrs = element.attrib

        for field in ("text", "content-desc"):

            value = attrs.get(field, "").strip()

            if (
                "task marked active" in value.lower()
                or "task marked complete" in value.lower()
            ):
                messages.append(value)

    return list(dict.fromkeys(messages))


# ================================================
# 觀察 Snackbar
# ================================================

def observe_snackbar(driver, seconds=1.5):

    messages = []

    end_time = time.monotonic() + seconds

    while time.monotonic() < end_time:

        xml_text = driver.page_source

        for message in find_snackbar(xml_text):

            if message not in messages:
                messages.append(message)

        if messages:
            break

        time.sleep(0.6)

    return messages


# ================================================
# 寫入 CSV 報告
# ================================================

def write_report(row):

    exists = REPORT_FILE.exists()

    with open(
        REPORT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=list(row.keys())
        )

        if not exists or REPORT_FILE.stat().st_size == 0:
            writer.writeheader()

        writer.writerow(row)


# ================================================
# 主測試流程
# ================================================

def main():

    driver = None

    initial = None
    completed = None
    active = None
    details = None

    snackbar_messages = []

    status = "ERROR"
    reason = "測試未完成"

    options = UiAutomator2Options()

    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"

    options.device_name = "Pixel 6"
    options.udid = "emulator-5554"

    options.app_package = APP_PACKAGE
    options.app_activity = APP_ACTIVITY

    options.no_reset = True

    try:

        print("=" * 55)
        print("GH-969 Checkbox / UI State Test V2")
        print("=" * 55)

        # =====================================
        # 1. 連接 Appium
        # =====================================

        print("\n[1] 連接 Appium...")

        driver = webdriver.Remote(
            SERVER_URL,
            options=options
        )

        print("Appium 連線成功")

        # =====================================
        # 2. 確認 Task List
        # =====================================

        print("\n[2] 確認 Task List...")

        wait_text(driver, TASK_TITLE)

        initial = checkbox_state(driver)

        print("初始 checked：", initial)

        save_evidence(driver, "01_initial")

        # =====================================
        # 3. 初始化為未完成
        # =====================================

        if initial:

            print("\n[3] 初始化：取消完成...")

            find_task_checkbox(driver).click()

            success = wait_checkbox_state(
                driver,
                False
            )

            if not success:

                current_state = checkbox_state(driver)

                save_evidence(
                    driver,
                    "02_uncheck_failed"
                )

                if current_state is True:

                    status = "SUSPECTED_UNCHECK_BUG"

                    reason = (
                        "初始化階段發現疑似異常："
                        "Appium 點擊已完成任務後，"
                        "Checkbox 仍維持 checked=True。"
                        "尚未完成後續 Task Details 驗證。"
                    )

                    raise SuspectedAppBug(reason)

                else:

                    status = "INCONCLUSIVE"

                    reason = (
                        "Checkbox 狀態等待失敗，"
                        "但重新讀取結果已變成未完成，"
                        "需要進一步確認。"
                    )

                    raise SuspectedAppBug(reason)

            save_evidence(
                driver,
                "02_reset_active"
            )

        # =====================================
        # 4. 勾選任務
        # =====================================

        print("\n[4] 勾選任務（完成）...")

        find_task_checkbox(driver).click()

        success = wait_checkbox_state(
            driver,
            True
        )

        completed = checkbox_state(driver)

        print("完成後 checked：", completed)

        save_evidence(driver, "03_completed")

        if not success or completed is not True:

            status = "INCONCLUSIVE"

            reason = (
                "勾選任務後，未能確認 "
                "Checkbox 已切換為完成。"
            )

            raise SuspectedAppBug(reason)

        # =====================================
        # 5. 取消勾選任務
        # =====================================

        print("\n[5] 取消勾選任務...")

        find_task_checkbox(driver).click()

        snackbar_messages = observe_snackbar(
            driver,
            seconds=1.5
        )

        print(
            "Snackbar：",
            snackbar_messages or "未捕捉到"
        )

        wait_checkbox_state(driver, False)

        active = checkbox_state(driver)

        print("取消後 checked：", active)

        save_evidence(
            driver,
            "04_after_uncheck"
        )

        # =====================================
        # 6. 進入 Task Details
        # =====================================

        print("\n[6] 進入 Task Details...")

        wait_text(driver, TASK_TITLE).click()

        time.sleep(0.5)

        save_evidence(
            driver,
            "05_task_details"
        )

        detail_boxes = driver.find_elements(
            AppiumBy.CLASS_NAME,
            "android.widget.CheckBox"
        )

        if detail_boxes:

            value = detail_boxes[0].get_attribute(
                "checked"
            )

            details = (
                str(value).lower() == "true"
            )

            print(
                "Details checked：",
                details
            )

        else:

            print(
                "Details Checkbox 未找到，"
                "需檢查 XML。"
            )

        # =====================================
        # 7. 分析測試結果
        # =====================================

        print("\n[7] 分析結果...")

        if (
            completed is True
            and active is False
            and details is False
        ):

            status = "CHECKBOX_PASS_VISUAL_PENDING"

            reason = (
                "Task List 與 Task Details "
                "的 Checkbox 均顯示未完成；"
                "文字刪除線仍需人工確認。"
            )

        elif active is True and details is False:

            status = "SUSPECTED_UI_SYNC_BUG"

            reason = (
                "Task List 取消完成後仍為 "
                "checked=True，"
                "但 Task Details 顯示 "
                "checked=False，兩頁狀態不一致。"
            )

        elif active is True:

            status = "SUSPECTED_BUG"

            reason = (
                "取消完成後 Checkbox "
                "仍維持 checked=True，"
                "需進一步確認 App 狀態更新問題。"
            )

        else:

            status = "INCONCLUSIVE"

            reason = (
                "部分 Checkbox 狀態無法確認，"
                "需要人工檢查 XML 與截圖。"
            )

        print("測試結果：", status)
        print("原因：", reason)

    # =====================================
    # 疑似 Bug 或測試未完成
    # =====================================

    except SuspectedAppBug as e:

        print("\n[測試提前停止]")

        print("狀態：", status)
        print("原因：", reason)

    # =====================================
    # 真正的執行錯誤
    # =====================================

    except Exception as e:

        status = "ERROR"
        reason = str(e)

        print("\n測試發生錯誤：", reason)

        if driver is not None:

            try:
                save_evidence(driver, "error")
            except Exception:
                pass

    # =====================================
    # 儲存結果與關閉 Appium
    # =====================================

    finally:

        row = {
            "issue_id": "GH-969",
            "run_id": RUN_ID,
            "task_title": TASK_TITLE,
            "initial_checked": initial,
            "completed_checked": completed,
            "active_checked": active,
            "details_checked": details,
            "snackbar_messages": " | ".join(
                snackbar_messages
            ),
            "status": status,
            "reason": reason,
            "evidence_dir": str(RUN_DIR)
        }

        try:

            write_report(row)

            print("\nCSV 報告儲存成功")

        finally:

            if driver is not None:

                try:
                    driver.quit()
                except Exception:
                    pass

        print("\n" + "=" * 55)

        print("GH-969 V2 測試結束")
        print("結果：", status)
        print("原因：", reason)
        print("報表：", REPORT_FILE)
        print("證據資料夾：", RUN_DIR)

        print("=" * 55)


# ================================================
# 自動更新 Dashboard
# ================================================

if __name__ == "__main__":

    main()

    print("\n開始更新 Dashboard 測試結果...")

    merge_script = (
        BASE_DIR / "merge_test_results.py"
    )

    try:

        subprocess.run(
            [
                sys.executable,
                str(merge_script)
            ],
            check=True
        )

        print("Dashboard CSV 更新完成！")

    except subprocess.CalledProcessError as e:

        print(
            "Dashboard CSV 更新失敗：",
            e
        )
