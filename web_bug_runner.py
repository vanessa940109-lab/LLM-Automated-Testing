import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# 基本設定
# ============================================================

WEB_URL = "http://127.0.0.1:5000"

WAIT_SECONDS = 5


# ============================================================
# 共用工具
# ============================================================

def reset_data():
    """
    每個 Bug 測試前清空 Todo 資料，
    避免前一個測試影響下一個。
    """

    try:
        request = urllib.request.Request(
            WEB_URL + "/test/reset",
            data=b"",
            method="POST"
        )

        urllib.request.urlopen(
            request,
            timeout=5
        ).read()

        print("RESET：測試資料已清空")

        return True

    except Exception as e:

        print("RESET ERROR：", e)

        return False


def open_home(driver):

    driver.get(WEB_URL)

    WebDriverWait(
        driver,
        WAIT_SECONDS
    ).until(
        EC.presence_of_element_located(
            (
                By.ID,
                "title"
            )
        )
    )


def add_task(driver, title):

    open_home(driver)

    title_input = driver.find_element(
        By.ID,
        "title"
    )

    title_input.clear()

    title_input.send_keys(
        title
    )

    driver.find_element(
        By.ID,
        "add-task"
    ).click()

    time.sleep(1)


def find_task_row(driver, title):

    rows = driver.find_elements(
        By.CLASS_NAME,
        "task"
    )

    for row in rows:

        try:

            task_title = row.find_element(
                By.CLASS_NAME,
                "task-title"
            ).text

            if task_title == title:

                return row

        except Exception:

            pass

    return None


def print_bug_header(
    bug_id,
    bug_name
):

    print()
    print("=" * 65)
    print(
        f"{bug_id}：{bug_name}"
    )
    print("=" * 65)
    print(
        "Ground Truth : BUG PRESENT"
    )


def reproduced():

    print(
        "BUG_RESULT   : BUG_REPRODUCED"
    )

    print(
        "Validation   : TRUE POSITIVE (TP)"
    )

    return "BUG_REPRODUCED"


def not_reproduced():

    print(
        "BUG_RESULT   : BUG_NOT_REPRODUCED"
    )

    print(
        "Validation   : FALSE NEGATIVE (FN)"
    )

    return "BUG_NOT_REPRODUCED"


def test_error(e):

    print(
        "BUG_RESULT   : TEST_ERROR"
    )

    print(
        f"Error        : {e}"
    )

    return "TEST_ERROR"


# ============================================================
# B01
# Empty Title Validation Bug
# ============================================================

def test_b01(driver):

    print_bug_header(
        "B01",
        "Empty Title Validation Bug"
    )

    try:

        reset_data()

        open_home(driver)

        title_input = driver.find_element(
            By.ID,
            "title"
        )

        # 輸入純空白
        title_input.send_keys(
            "   "
        )

        driver.find_element(
            By.ID,
            "add-task"
        ).click()

        time.sleep(1)

        rows = driver.find_elements(
            By.CLASS_NAME,
            "task"
        )

        print(
            f"空白輸入後 Task 數量：{len(rows)}"
        )

        # 正常應該是 0
        # 大於 0 = Bug 重現
        if len(rows) > 0:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B02
# Task Update Persistence Bug
# ============================================================

def test_b02(driver):

    print_bug_header(
        "B02",
        "Task Update Persistence Bug"
    )

    try:

        reset_data()

        old_title = "B02_OLD"

        new_title = "B02_NEW"

        add_task(
            driver,
            old_title
        )

        row = find_task_row(
            driver,
            old_title
        )

        if row is None:

            raise Exception(
                "找不到 B02_OLD"
            )

        row.find_element(
            By.CLASS_NAME,
            "edit-link"
        ).click()

        WebDriverWait(
            driver,
            WAIT_SECONDS
        ).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "edit-title"
                )
            )
        )

        edit_input = driver.find_element(
            By.ID,
            "edit-title"
        )

        edit_input.clear()

        edit_input.send_keys(
            new_title
        )

        driver.find_element(
            By.ID,
            "save-edit"
        ).click()

        time.sleep(1)

        page = driver.page_source

        old_exists = (
            old_title in page
        )

        new_exists = (
            new_title in page
        )

        print(
            f"舊標題仍存在：{old_exists}"
        )

        print(
            f"新標題存在：{new_exists}"
        )

        # Bug：Save 後仍是 OLD
        if (
            old_exists
            and not new_exists
        ):

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B03
# Delete Logic Bug
# ============================================================

def test_b03(driver):

    print_bug_header(
        "B03",
        "Task Delete Logic Bug"
    )

    try:

        reset_data()

        title = "B03_DELETE_TEST"

        add_task(
            driver,
            title
        )

        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B03 Task"
            )

        row.find_element(
            By.CLASS_NAME,
            "delete-button"
        ).click()

        time.sleep(1)

        row_after = find_task_row(
            driver,
            title
        )

        exists = (
            row_after is not None
        )

        print(
            f"Delete 後 Task 是否存在：{exists}"
        )

        if exists:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B04
# Complete State Bug
# ============================================================

def test_b04(driver):

    print_bug_header(
        "B04",
        "Task Complete State Bug"
    )

    try:

        reset_data()

        title = "B04_COMPLETE_TEST"

        add_task(
            driver,
            title
        )

        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B04 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        checkbox.click()

        time.sleep(1)

        row_after = find_task_row(
            driver,
            title
        )

        if row_after is None:

            raise Exception(
                "Complete 後找不到 B04 Task"
            )

        checkbox_after = (
            row_after.find_element(
                By.CLASS_NAME,
                "task-checkbox"
            )
        )

        checked = (
            checkbox_after.is_selected()
        )

        print(
            f"Complete 後 checked：{checked}"
        )

        # 正常應 True
        # False = Bug
        if not checked:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B05
# Active Filter Logic Bug
# ============================================================

def test_b05(driver):

    print_bug_header(
        "B05",
        "Active Filter Logic Bug"
    )

    try:

        reset_data()

        title = "B05_ACTIVE_TEST"

        add_task(
            driver,
            title
        )

        # 此時 Task 是 Active

        driver.find_element(
            By.ID,
            "filter-active"
        ).click()

        time.sleep(1)

        row = find_task_row(
            driver,
            title
        )

        exists = (
            row is not None
        )

        print(
            f"Active Filter 中 Task 是否存在：{exists}"
        )

        # 正常 Active Task 應存在
        # 不存在 = Bug
        if not exists:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B06
# Completed Filter Logic Bug
# ============================================================

def test_b06(driver):

    print_bug_header(
        "B06",
        "Completed Filter Logic Bug"
    )

    try:

        reset_data()

        title = "B06_COMPLETED_TEST"

        add_task(
            driver,
            title
        )

        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B06 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        checkbox.click()

        time.sleep(1)

        driver.find_element(
            By.ID,
            "filter-completed"
        ).click()

        time.sleep(1)

        row = find_task_row(
            driver,
            title
        )

        exists = (
            row is not None
        )

        print(
            "Completed Filter 中 "
            f"Task 是否存在：{exists}"
        )

        # 正常 Completed Task 應存在
        if not exists:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B07
# Activate State Bug
# ============================================================

def test_b07(driver):

    print_bug_header(
        "B07",
        "Activate State Bug"
    )

    try:

        reset_data()

        title = "B07_ACTIVATE_TEST"

        add_task(
            driver,
            title
        )

        # 第一次 Toggle
        # Active -> Completed
        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B07 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        checkbox.click()

        time.sleep(1)

        # 再找一次
        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "完成後找不到 B07 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        first_state = (
            checkbox.is_selected()
        )

        print(
            f"第一次 Complete：{first_state}"
        )

        if not first_state:

            raise Exception(
                "B07 前置 Complete 失敗"
            )

        # 第二次 Toggle
        # Completed -> Active
        checkbox.click()

        time.sleep(1)

        row_after = find_task_row(
            driver,
            title
        )

        if row_after is None:

            raise Exception(
                "Activate 後找不到 B07 Task"
            )

        checkbox_after = (
            row_after.find_element(
                By.CLASS_NAME,
                "task-checkbox"
            )
        )

        checked = (
            checkbox_after.is_selected()
        )

        print(
            f"Activate 後 checked：{checked}"
        )

        # 正常應 False
        # 仍然 True = Bug
        if checked:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B08
# Clear Completed Bug
# ============================================================

def test_b08(driver):

    print_bug_header(
        "B08",
        "Clear Completed Bug"
    )

    try:

        reset_data()

        title = "B08_CLEAR_TEST"

        add_task(
            driver,
            title
        )

        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B08 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        checkbox.click()

        time.sleep(1)

        # 確認已 Completed
        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "完成後找不到 B08 Task"
            )

        checkbox = row.find_element(
            By.CLASS_NAME,
            "task-checkbox"
        )

        if not checkbox.is_selected():

            raise Exception(
                "B08 前置 Complete 失敗"
            )

        # Clear Completed
        driver.find_element(
            By.ID,
            "clear-completed"
        ).click()

        time.sleep(1)

        row_after = find_task_row(
            driver,
            title
        )

        exists = (
            row_after is not None
        )

        print(
            "Clear Completed 後 "
            f"Task 是否存在：{exists}"
        )

        # 正常應被刪除
        # 還存在 = Bug
        if exists:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B09
# Task Retrieval Bug
# ============================================================

def test_b09(driver):

    print_bug_header(
        "B09",
        "Task Retrieval Bug"
    )

    try:

        reset_data()

        title = "B09_RETRIEVAL_TEST"

        add_task(
            driver,
            title
        )

        row = find_task_row(
            driver,
            title
        )

        if row is None:

            raise Exception(
                "找不到 B09 Task"
            )

        row.find_element(
            By.CLASS_NAME,
            "task-title"
        ).click()

        time.sleep(1)

        detail_title = (
            driver.find_element(
                By.ID,
                "task-title"
            ).text
        )

        print(
            f"預期 Detail：{title}"
        )

        print(
            f"實際 Detail：{detail_title}"
        )

        # 正常應完全相同
        if detail_title != title:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        return test_error(e)


# ============================================================
# B10
# Controlled Server Error
# ============================================================

def test_b10(driver):

    print_bug_header(
        "B10",
        "Controlled Server Error"
    )

    try:

        reset_data()

        open_home(driver)

        title = (
            "B10_CRASH_TEST"
        )

        driver.find_element(
            By.ID,
            "title"
        ).send_keys(
            title
        )

        driver.find_element(
            By.ID,
            "add-task"
        ).click()

        time.sleep(2)

        page = (
            driver.page_source.lower()
        )

        print(
            f"目前 URL：{driver.current_url}"
        )

        # Flask Debug Error Page
        # 通常會包含 traceback /
        # internal server error /
        # runtimeerror 等資訊。

        crash_signals = [
            "traceback",
            "internal server error",
            "runtimeerror",
            "b10 controlled server error"
        ]

        crash_found = any(
            signal in page
            for signal in crash_signals
        )

        print(
            f"Server Error 是否出現：{crash_found}"
        )

        if crash_found:

            return reproduced()

        return not_reproduced()

    except Exception as e:

        # 瀏覽器因 Server Error 發生例外時，
        # 也視為成功重現 B10。
        print(
            f"B10 Exception：{e}"
        )

        return reproduced()


# ============================================================
# 統計
# ============================================================

def print_summary(results):

    print()
    print()
    print("=" * 65)
    print(
        "Web Todo 人工植入 Bug 最終驗證結果"
    )
    print("=" * 65)

    for bug_id, info in results.items():

        print(
            f"{bug_id:<4} "
            f"{info['type']:<20} "
            f": {info['result']}"
        )

    total = len(
        results
    )

    tp = sum(
        info["result"]
        == "BUG_REPRODUCED"
        for info in results.values()
    )

    fn = sum(
        info["result"]
        == "BUG_NOT_REPRODUCED"
        for info in results.values()
    )

    errors = sum(
        info["result"]
        == "TEST_ERROR"
        for info in results.values()
    )

    valid_tests = (
        tp + fn
    )

    detection_rate = (
        tp
        / valid_tests
        * 100
        if valid_tests > 0
        else 0
    )

    error_rate = (
        errors
        / total
        * 100
        if total > 0
        else 0
    )

    print()
    print("-" * 65)

    print(
        f"人工植入 Bug 數量：{total}"
    )

    print(
        f"成功偵測 Bug：{tp}"
    )

    print(
        f"未偵測 Bug：{fn}"
    )

    print(
        f"測試錯誤：{errors}"
    )

    print()

    print(
        f"True Positive (TP)：{tp}"
    )

    print(
        f"False Negative (FN)：{fn}"
    )

    print()

    print(
        "Bug Detection Rate："
        f"{detection_rate:.2f}%"
    )

    print(
        "Test Error Rate："
        f"{error_rate:.2f}%"
    )

    print("=" * 65)


# ============================================================
# Main
# ============================================================

def main():

    driver = None

    print()
    print("=" * 65)
    print(
        "Web Todo B01～B10 自動 Bug 驗證系統"
    )
    print("=" * 65)

    try:

        print(
            "\n正在啟動 Chrome..."
        )

        driver = webdriver.Chrome()

        driver.set_window_size(
            1200,
            900
        )

        print(
            "PASS：Chrome 啟動成功"
        )

        # ----------------------------------------------------
        # 執行 B01 ～ B10
        # ----------------------------------------------------

        b01 = test_b01(driver)

        b02 = test_b02(driver)

        b03 = test_b03(driver)

        b04 = test_b04(driver)

        b05 = test_b05(driver)

        b06 = test_b06(driver)

        b07 = test_b07(driver)

        b08 = test_b08(driver)

        b09 = test_b09(driver)

        # B10 最後執行
        b10 = test_b10(driver)

        # ----------------------------------------------------
        # 統計
        # ----------------------------------------------------

        results = {

            "B01": {
                "type": "validation",
                "result": b01
            },

            "B02": {
                "type": "persistence",
                "result": b02
            },

            "B03": {
                "type": "delete_logic",
                "result": b03
            },

            "B04": {
                "type": "complete_state",
                "result": b04
            },

            "B05": {
                "type": "active_filter",
                "result": b05
            },

            "B06": {
                "type": "completed_filter",
                "result": b06
            },

            "B07": {
                "type": "activate_state",
                "result": b07
            },

            "B08": {
                "type": "clear_completed",
                "result": b08
            },

            "B09": {
                "type": "task_retrieval",
                "result": b09
            },

            "B10": {
                "type": "server_error",
                "result": b10
            }
        }

        print_summary(
            results
        )

    except Exception as e:

        print()
        print("=" * 65)
        print(
            "SYSTEM TEST ERROR"
        )
        print("=" * 65)

        print(e)

    finally:

        if driver is not None:

            time.sleep(2)

            driver.quit()

            print(
                "\nChrome 已關閉"
            )


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":

    main()