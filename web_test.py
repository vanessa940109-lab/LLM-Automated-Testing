import time

from selenium import webdriver
from selenium.webdriver.common.by import By


# ============================================================
# 基本設定
# ============================================================

WEB_URL = "http://127.0.0.1:5000"


# ============================================================
# 建立 Chrome Driver
# ============================================================

print("=" * 60)
print("Web Todo Selenium 自動測試")
print("=" * 60)

driver = webdriver.Chrome()

try:

    # --------------------------------------------------------
    # Step 1：開啟 Todo Web
    # --------------------------------------------------------

    print("\n[Step 1] 開啟 Todo Web")

    driver.get(WEB_URL)

    time.sleep(2)

    print("PASS：成功開啟 Todo Web")


    # --------------------------------------------------------
    # Step 2：找到 Title 輸入框
    # --------------------------------------------------------

    print("\n[Step 2] 尋找 Task Title 輸入框")

    title_input = driver.find_element(
        By.ID,
        "title"
    )

    print("PASS：找到 Title 輸入框")


    # --------------------------------------------------------
    # Step 3：輸入測試資料
    # --------------------------------------------------------

    test_title = "SELENIUM_TEST_001"

    print(
        f"\n[Step 3] 輸入 Task：{test_title}"
    )

    title_input.send_keys(test_title)

    print("PASS：輸入完成")


    # --------------------------------------------------------
    # Step 4：按 Add Task
    # --------------------------------------------------------

    print("\n[Step 4] 點擊 Add Task")

    add_button = driver.find_element(
        By.ID,
        "add-task"
    )

    add_button.click()

    time.sleep(2)

    print("PASS：已點擊 Add Task")


    # --------------------------------------------------------
    # Step 5：驗證 Task 是否出現
    # --------------------------------------------------------

    print("\n[Step 5] 驗證新增結果")

    page = driver.page_source

    if test_title in page:

        print(
            f"PASS：找到 {test_title}"
        )

        print()
        print("=" * 60)
        print("TEST RESULT：PASS")
        print("=" * 60)

    else:

        print(
            f"FAIL：找不到 {test_title}"
        )

        print()
        print("=" * 60)
        print("TEST RESULT：FAIL")
        print("=" * 60)


except Exception as e:

    print()
    print("=" * 60)
    print("TEST RESULT：ERROR")
    print("=" * 60)

    print(e)


finally:

    time.sleep(3)

    driver.quit()

    print("\nChrome 已關閉")