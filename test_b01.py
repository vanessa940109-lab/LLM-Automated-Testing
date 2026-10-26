
# -*- coding: utf-8 -*-

from selenium import webdriver
from llm_planner import load_bug_cases
from llm_executor import run_case

def main():
    # 讀取所有 Bug 案例
    bugs = load_bug_cases()

    # 找到 B02 測試案例
    bug = next(
        b for b in bugs
        if b["id"] == "B02"
    )

    print("開始執行 B02 測試")

    driver = None

    try:
        # 啟動 Chrome
        driver = webdriver.Chrome()

        # 執行 B02
        result = run_case(driver, bug)

        # 顯示測試結果
        print("\n========== 測試結果 ==========")
        print("Bug ID:", result["bug_id"])
        print("JSON 驗證:", result["plan_valid"])
        print("測試結果:", result["test_result"])
        print("錯誤訊息:", result["error_message"])
        print("==============================")

    finally:
        # 關閉 Chrome
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
