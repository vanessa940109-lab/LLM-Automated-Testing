
# ==================================================
# GitHub Bug Test Planner
# 第二步：讀取並篩選可自動測試的 GitHub Bug
# ==================================================

import json
from pathlib import Path

# 取得目前程式所在資料夾
BASE_DIR = Path(__file__).resolve().parent

# 原本的分類結果
INPUT_FILE = BASE_DIR / "bug_classification_results.json"


# 讀取分類結果
def load_results():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    return data


# 篩選可自動測試的 Bug
def filter_testable_bugs(data):

    selected = []

    for issue in data:

        # 只選分類成功的資料
        if issue.get("status") != "SUCCESS":
            continue

        # 必須被判斷為 Bug
        if issue.get("is_bug") is not True:
            continue

        # 必須被判斷為可測試
        if issue.get("testable") is not True:
            continue

        selected.append(issue)

    return selected


# 主程式
def main():

    print("=" * 55)
    print("GitHub Bug Test Planner")
    print("=" * 55)

    # 讀取資料
    data = load_results()

    print(f"GitHub Issues 總數：{len(data)}")

    # 篩選 Bug
    bugs = filter_testable_bugs(data)

    print(f"可自動測試的 Bug：{len(bugs)}")

    print()
    print("=" * 55)
    print("可測試 Bug 清單")
    print("=" * 55)

    for bug in bugs:

        print()
        print(f"Issue ID：{bug.get('issue_id')}")
        print(f"標題：{bug.get('title')}")
        print(f"分類：{bug.get('category')}")
        print(f"測試類型：{bug.get('test_type')}")

    print()
    print("資料篩選完成！")


if __name__ == "__main__":
    main()
