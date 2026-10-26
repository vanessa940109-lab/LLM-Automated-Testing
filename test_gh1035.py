
# ==========================================
# GH-1035 Android Appium 自動化測試
# 返回按鈕 + 快速開啟側邊選單
# ==========================================

import csv
import time
from pathlib import Path
from datetime import datetime

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait


SERVER_URL = "http://127.0.0.1:4723"

APP_PACKAGE = (
    "com.example.android.architecture.blueprints.main"
)

APP_ACTIVITY = (
    "com.example.android.architecture.blueprints.todoapp.TodoActivity"
)

TEST_ROUNDS = 5

BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "gh1035_results"

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = RESULT_DIR / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

REPORT_FILE = RESULT_DIR / "gh1035_report.csv"


def wait_accessibility(driver, name, timeout=12):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_elements(
            AppiumBy.ACCESSIBILITY_ID,
            name
        )
    )[0]


def wait_text(driver, text, timeout=12):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_elements(
            AppiumBy.XPATH,
            f'//*[@text="{text}"]'
        )
    )[0]


def click_menu(driver, text):
    xpath = (
        f'//*[@text="{text}"]'
        "/ancestor::*[@clickable='true'][1]"
    )
    driver.find_element(AppiumBy.XPATH, xpath).click()


def save_evidence(driver, name):
    """每回合只儲存一次截圖及 XML。"""

    screenshot = RUN_DIR / f"{name}.png"
    xml_file = RUN_DIR / f"{name}.xml"

    driver.save_screenshot(str(screenshot))
    xml_file.write_text(
        driver.page_source,
        encoding="utf-8"
    )


def check_drawer(driver):
    """確認側邊選單是否正常顯示。"""

    xml_text = driver.page_source

    has_task_list = 'text="Task List"' in xml_text
    has_statistics = 'text="Statistics"' in xml_text

    return has_task_list and has_statistics


def write_report(rows, final_status):
    """儲存每回合的測試結果。"""

    fieldnames = [
        "issue_id",
        "run_id",
        "round",
        "elapsed_seconds",
        "status",
        "reason"
    ]

    with open(
        REPORT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        if f.tell() == 0:
            writer.writeheader()

        writer.writerows(rows)

    print("\n" + "=" * 55)
    print("GH-1035 測試結束")
    print("總回合：", len(rows))
    print("整體結果：", final_status)
    print("報表：", REPORT_FILE)
    print("證據資料夾：", RUN_DIR)
    print("=" * 55)


def main():

    driver = None
    results = []
    final_status = "ERROR"

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
        print("GH-1035 Navigation Bug 自動化測試")
        print("=" * 55)

        print("\n[1] 連接 Appium...")

        driver = webdriver.Remote(
            SERVER_URL,
            options=options
        )

        print("Appium 連線成功")

        wait_accessibility(driver, "New Task")

        # ==================================
        # 執行多回合測試
        # ==================================

        for round_number in range(1, TEST_ROUNDS + 1):

            print("\n" + "-" * 45)
            print("測試回合：", round_number)
            print("-" * 45)

            start_time = time.perf_counter()

            try:
                # 1. 進入 New Task
                print("[1] 開啟 New Task")

                wait_accessibility(
                    driver,
                    "New Task"
                ).click()

                wait_accessibility(
                    driver,
                    "Back"
                )

                # 2. 返回 Task List
                print("[2] 返回 Task List")

                driver.find_element(
                    AppiumBy.ACCESSIBILITY_ID,
                    "Back"
                ).click()

                # 3. 立即嘗試點擊 Drawer
                print("[3] 立即點擊 Open Drawer")

                # 不額外 sleep，盡快尋找按鈕
                wait_accessibility(
                    driver,
                    "Open Drawer",
                    timeout=5
                ).click()

                # 4. 檢查選單是否正常
                print("[4] 檢查畫面")

                time.sleep(0.5)

                drawer_ok = check_drawer(driver)

                elapsed = time.perf_counter() - start_time

                if drawer_ok:

                    status = "NOT_REPRODUCED"
                    reason = (
                        "返回後側邊選單正常顯示，"
                        "本回合未觀察到空白畫面。"
                    )

                else:

                    status = "SUSPECTED_BLANK"
                    reason = (
                        "側邊選單未顯示預期內容，"
                        "可能是空白畫面或載入延遲，"
                        "需要檢查截圖與 XML。"
                    )

                save_evidence(
                    driver,
                    f"round_{round_number}"
                )

                results.append({
                    "issue_id": "GH-1035",
                    "run_id": RUN_ID,
                    "round": round_number,
                    "elapsed_seconds": round(elapsed, 3),
                    "status": status,
                    "reason": reason
                })

                print("結果：", status)
                print("耗時：", round(elapsed, 3), "秒")

                # 5. 返回 Task List，準備下一回合
                if drawer_ok:
                    click_menu(driver, "Task List")
                    wait_accessibility(driver, "New Task")
                else:
                    print(
                        "畫面異常，停止測試，"
                        "避免繼續操作造成狀態混亂。"
                    )
                    break

            except Exception as e:

                print("本回合發生錯誤：", e)

                elapsed = time.perf_counter() - start_time

                results.append({
                    "issue_id": "GH-1035",
                    "run_id": RUN_ID,
                    "round": round_number,
                    "elapsed_seconds": round(elapsed, 3),
                    "status": "ERROR",
                    "reason": str(e)
                })

                try:
                    save_evidence(
                        driver,
                        f"round_{round_number}_error"
                    )
                except Exception:
                    pass

                break

        # ==================================
        # 統計結果
        # ==================================

        statuses = [
            row["status"]
            for row in results
        ]

        if "SUSPECTED_BLANK" in statuses:
            final_status = "NEEDS_REVIEW"

        elif "ERROR" in statuses:
            final_status = "ERROR"

        elif (
            len(results) == TEST_ROUNDS
            and all(
                x == "NOT_REPRODUCED"
                for x in statuses
            )
        ):
            final_status = "NOT_REPRODUCED"

        else:
            final_status = "INCONCLUSIVE"

    except Exception as e:

        print("\n連線或初始化失敗：", e)
        final_status = "ERROR"

    finally:

        write_report(
            results,
            final_status
        )

        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass



if __name__ == "__main__":
    main()

    # 測試完成後，自動更新 Dashboard CSV
    import subprocess
    import sys
    from pathlib import Path

    print("\n開始更新 Dashboard 測試結果...")

    merge_script = (
        Path(__file__).resolve().parent
        / "merge_test_results.py"
    )

    try:
        subprocess.run(
            [sys.executable, str(merge_script)],
            check=True
        )

        print("Dashboard CSV 更新完成！")

    except subprocess.CalledProcessError as e:
        print("Dashboard CSV 更新失敗：", e)

