
# ============================================
# GH-1046 Snackbar Bug 自動化驗證
# Pixel 6 + Appium + UiAutomator2
#
# 測試內容：
# 1. 確認 Todo 首頁
# 2. 切換 Statistics
# 3. 返回 Task List
# 4. 檢查 Task saved 是否再次出現
# 5. 重複測試兩次
# 6. 儲存 CSV、XML 與截圖
#
# 注意：
# 不新增、不編輯、不刪除任何任務
# ============================================

import csv
import time
from pathlib import Path
from datetime import datetime
from xml.etree import ElementTree as ET

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

TASK_TITLE = "GH1046_Test_142710"

BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = BASE_DIR / "gh1046_verify_results"

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = RESULT_DIR / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

REPORT_FILE = RESULT_DIR / "gh1046_verify_report.csv"

# 每次返回列表後觀察 2 秒
OBSERVE_SECONDS = 2.0

# 避免高頻擷取造成 UiAutomator2 不穩定
POLL_INTERVAL = 0.5

# 重複切換次數
TEST_ROUNDS = 2


def wait_for_text(driver, text, timeout=15):
    return WebDriverWait(driver, timeout).until(
        lambda d: d.find_elements(
            AppiumBy.XPATH,
            f'//*[@text="{text}"]'
        )
    )

def ensure_task_list(driver):
    """
    確保測試開始前位於 Task List 頁面。
    如果目前在任務詳細頁面，就先返回。
    """

    back_buttons = driver.find_elements(
        AppiumBy.ACCESSIBILITY_ID,
        "Back"
    )

    if back_buttons:
        print("[DEBUG] 目前在任務詳細頁面，準備返回 Task List")
        back_buttons[0].click()
        time.sleep(1)

    print("[DEBUG] 已完成 Task List 畫面檢查")



def click_accessibility(driver, description):
    driver.find_element(
        AppiumBy.ACCESSIBILITY_ID,
        description
    ).click()


def click_menu_text(driver, text):
    xpath = (
        f'//*[@text="{text}"]'
        "/ancestor::*[@clickable='true'][1]"
    )

    driver.find_element(
        AppiumBy.XPATH,
        xpath
    ).click()


def find_task_saved(xml_text):
    """
    從 XML 尋找 Task saved。

    注意：Snackbar 可能顯示時間很短，
    沒找到不代表沒有出現。
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False

    for element in root.iter():
        attrs = element.attrib

        text = attrs.get("text", "").strip().lower()
        desc = attrs.get("content-desc", "").strip().lower()

        if "task saved" in text or "task saved" in desc:
            return True

    return False


def save_evidence(driver, name, xml_text=None):
    screenshot = RUN_DIR / f"{name}.png"
    xml_file = RUN_DIR / f"{name}.xml"

    driver.save_screenshot(str(screenshot))

    if xml_text is None:
        xml_text = driver.page_source

    xml_file.write_text(
        xml_text,
        encoding="utf-8"
    )

    print("已儲存證據：", name)


def observe_task_saved(driver, round_number):
    """
    返回 Task List 後，
    觀察是否出現 Task saved。
    """

    print(
        f"\n[Round {round_number}] "
        "觀察 Task saved..."
    )

    end_time = time.monotonic() + OBSERVE_SECONDS
    detected = False
    samples = 0

    while time.monotonic() < end_time:

        samples += 1

        xml_text = driver.page_source

        if find_task_saved(xml_text):
            detected = True

            save_evidence(
                driver,
                f"round_{round_number}_task_saved",
                xml_text
            )

            print("偵測到 Task saved！")
            break

        time.sleep(POLL_INTERVAL)

    print("XML 擷取次數：", samples)

    if not detected:
        print(
            "未在 XML 中偵測到 Task saved，"
            "不代表 Snackbar 沒有出現。"
        )

    return detected


def write_report(status, results, reason):

    row = {
        "issue_id": "GH-1046",
        "run_id": RUN_ID,
        "status": status,
        "rounds": TEST_ROUNDS,
        "detected_rounds": sum(results),
        "round_results": "|".join(
            str(x) for x in results
        ),
        "reason": reason,
        "evidence_dir": str(RUN_DIR)
    }

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

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def main():

    driver = None
    results = []

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
        print("GH-1046 Snackbar Bug 自動化驗證")
        print("=" * 55)

        print("\n[1] 連接 Appium...")

        driver = webdriver.Remote(
            SERVER_URL,
            options=options
        )

        print("Appium 連線成功")

        print("\n[2] 確認 Todo 首頁...")

        wait_for_text(driver, TASK_TITLE)

        print("找到任務：", TASK_TITLE)

        save_evidence(driver, "before_test")

        # ====================================
        # 重複執行頁面切換
        # ====================================

        for round_number in range(
            1,
            TEST_ROUNDS + 1
        ):

            print("\n" + "-" * 45)
            print("測試回合：", round_number)
            print("-" * 45)

            # 進入 Statistics
            print("切換到 Statistics...")

            ensure_task_list(driver)
            
            print("[DEBUG] 準備開啟側邊選單", flush=True)

            click_accessibility(
                driver,
                "Open Drawer"
)

            print("[DEBUG] 側邊選單已開啟", flush=True)

            wait_for_text(
                driver,
                "Statistics"
)

            print("[DEBUG] 已找到 Statistics 文字", flush=True)

            click_menu_text(
                driver,
                "Statistics"
)

            print("[DEBUG] 已點擊 Statistics", flush=True)


            wait_for_text(
                driver,
                "Statistics"
            )

            # 返回 Task List
            print("返回 Task List...")

            click_accessibility(
                driver,
                "Open Drawer"
            )

            wait_for_text(
                driver,
                "Task List"
            )

            click_menu_text(
                driver,
                "Task List"
            )

            # 立即觀察 Snackbar
            detected = observe_task_saved(
                driver,
                round_number
            )

            results.append(detected)

            # 避免重複測試過快
            time.sleep(1)

        # ====================================
        # 分析結果
        # ====================================

        print("\n[3] 分析測試結果...")

        detected_count = sum(results)

        if detected_count > 0:

            status = "BUG_REPRODUCED"

            reason = (
                "在未執行新增或編輯任務操作的"
                "頁面切換過程中，"
                "Appium 偵測到 Task saved 文字。"
            )

        else:

            status = "INCONCLUSIVE"

            reason = (
                "完成頁面切換，但 XML 未捕捉到"
                "Task saved。Snackbar 可能短暫出現，"
                "不能判定 Bug 不存在。"
            )

        print("測試狀態：", status)
        print("偵測回合：", detected_count)
        print("原因：", reason)

    except Exception as e:

        status = "ERROR"
        reason = str(e)

        print("\n測試發生錯誤：", reason)

        if driver is not None:
            try:
                save_evidence(
                    driver,
                    "error"
                )
            except Exception:
                pass

    finally:

        write_report(
            status,
            results,
            reason
        )

        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

        print("\n" + "=" * 55)
        print("GH-1046 自動化驗證結束")
        print("結果：", status)
        print("報表：", REPORT_FILE)
        print("證據資料夾：", RUN_DIR)
        print("=" * 55)



if __name__ == "__main__":
    main()

    # Appium 測試完成後，自動合併 Dashboard CSV
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
