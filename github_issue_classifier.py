
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


# ==========================================
# 1. 基本設定
# ==========================================
BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "github_issues.json"
OUTPUT_FILE = BASE_DIR / "github_classification_v5.csv"

GROUND_TRUTH_FILE = BASE_DIR / "github_ground_truth.csv"
EVALUATION_FILE = BASE_DIR / "github_evaluation_v5.csv"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen2.5:3b"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 180

# True：測試指定 10 筆
# False：分類全部 Issues
TEST_MODE = True

TEST_ISSUE_IDS = [
    "GH-1081",
    "GH-1079",
    "GH-1076",
    "GH-1066",
    "GH-1049",
    "GH-1046",
    "GH-1045",
    "GH-1043",
    "GH-1035",
    "GH-969",
]

CATEGORIES = {
    "task_create",
    "task_edit",
    "task_delete",
    "task_complete",
    "task_filter",
    "snackbar",
    "navigation",
    "crash",
    "persistence",
    "performance",
    "network",
    "security",
    "build",
    "architecture",
    "documentation",
    "non_ui",
    "other",
}

FIELDS = [
    "issue_id",
    "title",
    "url",
    "is_bug",
    "category",
    "testable",
    "test_type",
    "reason",
    "suggested_test",
    "review_status",
    "model",
    "status",
    "attempts",
    "duration_seconds",
    "error_message",
]


# ==========================================
# 2. 讀取 Issues
# ==========================================
def load_issues():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"找不到檔案：{INPUT_FILE}"
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("issues", "items", "data"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError("GitHub Issues JSON 格式錯誤")


def get_description(issue):
    return str(
        issue.get("description")
        or issue.get("body")
        or ""
    ).strip()


def get_labels(issue):
    labels = issue.get("labels") or []
    return json.dumps(labels, ensure_ascii=False)


# ==========================================
# 3. 標準結果
# ==========================================
def make_result(
    is_bug=None,
    category="other",
    testable=None,
    test_type="unknown",
    reason="",
    suggested_test="Not applicable",
    review_status="PENDING",
):
    return {
        "is_bug": is_bug,
        "category": category,
        "testable": testable,
        "test_type": test_type,
        "reason": reason,
        "suggested_test": suggested_test,
        "review_status": review_status,
    }


# ==========================================
# 4. 第一階段：資料品質檢查
# ==========================================
def quality_check(issue):
    title = str(issue.get("title") or "").strip()
    description = get_description(issue)

    if not title and not description:
        return "Title and description are empty."

    if not description:
        parsed = urlparse(title)

        if (
            parsed.scheme in ("http", "https")
            and parsed.netloc
        ):
            return "Issue contains only a URL."

        placeholders = {
            "test", "testing", "hello",
            "hi", "p1", "123",
            "issue", "bug",
        }

        if title.lower() in placeholders:
            return "Placeholder title without description."

        if len(title) < 15:
            return "Title too short without description."

        letters = sum(c.isalpha() for c in title)

        if letters < 4:
            return "Insufficient textual information."

    return None


# ==========================================
# 5. 呼叫 Ollama
# ==========================================
def extract_json(text):
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)

        if not match:
            raise ValueError("LLM 沒有回傳 JSON")

        data = json.loads(match.group())

    if not isinstance(data, dict):
        raise ValueError("LLM 回傳格式不是物件")

    return data


def ask_ollama(prompt):
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    raw = response.json().get("response", "")

    return extract_json(raw)


# ==========================================
# 6. 第二階段：Bug 候選判斷
# ==========================================


def classify_bug(issue):
    title = str(issue.get("title") or "").strip()
    description = get_description(issue)
    labels = get_labels(issue)

    prompt = f"""
You are a software issue triage assistant.

Repository:
android/architecture-samples

TASK:
Classify whether this GitHub Issue reports a
POSSIBLE SOFTWARE DEFECT.

You are identifying bug report candidates.
You are NOT confirming that a bug exists.

DECISION DEFINITIONS:

BUG:
A concrete unexpected software behavior,
functional failure, incorrect UI state,
or plausible security weakness is described.

NOT_BUG:
The report is clearly unrelated to this
repository, a test message, an advertisement,
a feature request, or a general question
without a reported defect.

UNCERTAIN:
The report suggests a potentially relevant
software problem but the abnormal behavior
cannot be identified reliably.

IMPORTANT RULES:

1. A report describing a blank screen,
   repeated snackbar, incorrect checkbox
   state, lost task data, or failed
   navigation is a BUG CANDIDATE.

2. Do not require screenshots, logs,
   reproduction steps, or confirmed
   root causes for bug candidate detection.

3. A potential Android security weakness,
   such as an exported component with
   insufficient access protection, may
   qualify as a BUG CANDIDATE.

4. An exported component is not automatically
   a vulnerability. Consider whether the
   report identifies a plausible risk.

5. If the report describes a specific
   unexpected behavior, do not choose
   UNCERTAIN solely because reproduction
   has not been confirmed.

6. If the report is clearly unrelated,
   a placeholder, or a test message,
   choose NOT_BUG.

7. If information is insufficient and
   relevance cannot be established,
   choose UNCERTAIN and begin the reason
   with "INSUFFICIENT:".

8. Do not invent missing behavior,
   reproduction steps, or security impact.

9. Do not classify something as a bug
   merely because technical terminology
   or code is present.

ISSUE TITLE:
{title}

ISSUE DESCRIPTION:
{description[:4000]}

ISSUE LABELS:
{labels}

Return ONLY valid JSON:

{{
    "decision": "BUG",
    "reason": "Short explanation supported by the issue."
}}

The decision must be exactly one of:
BUG, NOT_BUG, UNCERTAIN.

The JSON example is only a format example,
not a suggested classification.
"""

    result = ask_ollama(prompt)

    decision = str(
        result.get("decision") or ""
    ).strip().upper()

    reason = str(
        result.get("reason") or ""
    ).strip()

    if decision not in {
        "BUG",
        "NOT_BUG",
        "UNCERTAIN"
    }:
        raise ValueError(
            f"Invalid bug decision: {decision}"
        )

    if not reason:
        raise ValueError("Invalid bug reason")

    return {
        "decision": decision,
        "reason": reason,
    }




# ==========================================
# 7. 第三階段：類別與 UI 可測試性
# ==========================================

def classify_testability(issue):
    title = str(issue.get("title") or "").strip()
    description = get_description(issue)
    labels = get_labels(issue)

    prompt = f"""
You are an Android UI test planning assistant.

Repository:
android/architecture-samples

The issue has already been classified
as a POSSIBLE SOFTWARE BUG.

Your tasks are:
1. Identify the main defect category.
2. Decide whether an Android UI test
   scenario can be DESIGNED from the report.
3. Suggest a meaningful test scenario.

IMPORTANT:
You are evaluating TEST DESIGN FEASIBILITY,
not whether a test has already succeeded.

CATEGORY DEFINITIONS:

task_create:
Failure to create or save a task.

task_edit:
Failure to edit or update a task.

task_delete:
Failure to delete a task.

task_complete:
Incorrect checkbox state, completion
state, strikethrough, or task status.

task_filter:
Incorrect task filtering behavior.

snackbar:
Incorrect, repeated, missing, or
unexpected snackbar messages.

navigation:
Blank screens, back button failures,
drawer failures, or screen transitions.

crash:
Application crashes or exceptions.

persistence:
Task data is lost or not retained.

performance:
Slowness or excessive resource use.

network:
Network communication or sync defects.

security:
Permission or unauthorized access risks.

build:
Compilation or build failures.

architecture:
Software architecture or structural defects
without a more specific behavioral category.

documentation:
Documentation defects.

non_ui:
Other non-UI defects.

other:
Defects that cannot be categorized.

CATEGORY RULES:

- Choose the category based on the
  REPORTED FAILURE, not the file name.

- If task completion changes but its
  displayed state is incorrect,
  choose task_complete.

- If a snackbar repeats unexpectedly,
  choose snackbar.

- If navigation produces a blank screen,
  choose navigation.

- Do not choose architecture merely
  because the report includes source code.

- Prefer the most specific category.

ANDROID UI TEST CANDIDATE RULES:

Set testable = true when BOTH conditions hold:

A. The report identifies an Android UI
   action or visible application state.

B. The report identifies an observable
   expected or unexpected result.

Examples of suitable UI scenarios:

- Create or edit a task, navigate away,
  return, and verify that a snackbar
  does not unexpectedly repeat.

- Navigate back from an edit screen,
  quickly open the drawer, and verify
  that the screen is not blank.

- Toggle a completed task back to
  incomplete and verify that the
  strikethrough is removed.

These examples describe test DESIGN,
not proof that a bug exists.

DO NOT require:
- Existing Appium code.
- Known element selectors.
- Screenshots.
- Complete reproduction instructions.
- Confirmed reproduction.
- A known root cause.

Set testable = false when:
- The defect is purely about security
  configuration or static analysis.
- The defect is build-only.
- There is no identifiable Android UI
  action or observable UI result.
- The report lacks enough information
  to design a meaningful UI assertion.

TEST TYPE:

If testable is true:
test_type must be "android_ui".

If testable is false:
test_type must be "non_ui" or "unknown".

SUGGESTED TEST:

For testable = true:
Provide a short scenario containing:
- User actions.
- Expected observable result.

For testable = false:
Use "Not applicable".

Do not invent:
- Appium selectors.
- Resource IDs.
- Screen names not mentioned.
- Features not supported by the report.

ISSUE TITLE:
{title}

ISSUE DESCRIPTION:
{description[:4000]}

ISSUE LABELS:
{labels}

Return ONLY one valid JSON object
with these five fields:

category
testable
test_type
reason
suggested_test

FIELD REQUIREMENTS:

category:
One of the categories defined above.

testable:
A JSON boolean, true or false.

test_type:
One of android_ui, non_ui, unknown.

reason:
Briefly explain the classification
using evidence from the issue.

suggested_test:
A proposed UI interaction and expected
result, or "Not applicable".

Make an independent decision.
Do not use default values.
"""

    result = ask_ollama(prompt)

    category = str(
        result.get("category") or ""
    ).strip().lower()

    testable = result.get("testable")

    test_type = str(
        result.get("test_type") or ""
    ).strip().lower()

    reason = str(
        result.get("reason") or ""
    ).strip()

    suggested = str(
        result.get("suggested_test") or ""
    ).strip()

    if category not in CATEGORIES:
        raise ValueError(
            f"Invalid category: {category}"
        )

    if type(testable) is not bool:
        raise ValueError(
            f"Invalid testable value: {testable}"
        )

    if test_type not in {
        "android_ui",
        "non_ui",
        "unknown"
    }:
        raise ValueError(
            f"Invalid test_type: {test_type}"
        )

    if not reason:
        raise ValueError(
            "Invalid testability reason"
        )

    if testable:
        if (
            not suggested
            or suggested.lower() == "not applicable"
        ):
            raise ValueError(
                "UI candidate has no test scenario"
            )

        test_type = "android_ui"

    else:
        if test_type == "android_ui":
            test_type = "unknown"

        suggested = "Not applicable"

    return {
        "category": category,
        "testable": testable,
        "test_type": test_type,
        "reason": reason,
        "suggested_test": suggested,
    }



# ==========================================
# 8. 分類流程 + 重試
# ==========================================
def classify_issue(issue):
    quality_reason = quality_check(issue)

    if quality_reason is not None:
        return (
            make_result(
                is_bug=None,
                testable=None,
                reason=quality_reason,
                review_status="INSUFFICIENT",
            ),
            "FILTERED",
            0,
        )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            bug = classify_bug(issue)

            if bug["decision"] == "UNCERTAIN":
                return (
                    make_result(
                        is_bug=None,
                        testable=None,
                        reason=bug["reason"],
                        review_status="NEEDS_REVIEW",
                    ),
                    "SUCCESS",
                    attempt,
                )

            if bug["decision"] == "NOT_BUG":
                return (
                    make_result(
                        is_bug=False,
                        testable=False,
                        reason=bug["reason"],
                        review_status="PENDING",
                    ),
                    "SUCCESS",
                    attempt,
                )

            test = classify_testability(issue)

            result = make_result(
                is_bug=True,
                category=test["category"],
                testable=test["testable"],
                test_type=test["test_type"],
                reason=(
                    bug["reason"]
                    + " | "
                    + test["reason"]
                ),
                suggested_test=test["suggested_test"],
                review_status="PENDING",
            )

            return result, "SUCCESS", attempt

        except (
            requests.RequestException,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            last_error = error

            print(
                f"第 {attempt}/{MAX_RETRIES} 次失敗："
                f"{error}"
            )

            if attempt < MAX_RETRIES:
                time.sleep(2)

    raise RuntimeError(
        f"LLM failed after {MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ==========================================
# 9. CSV 儲存
# ==========================================
def save_results(results):
    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS,
        )
        writer.writeheader()
        writer.writerows(results)


# ==========================================
# 10. 建立人工標準答案範本
# ==========================================
def create_ground_truth_template(issues):
    # 已存在時不覆蓋人工標註
    if GROUND_TRUTH_FILE.exists():
        return

    with open(
        GROUND_TRUTH_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_id",
                "title",
                "true_is_bug",
                "true_category",
                "true_testable",
                "review_notes",
            ],
        )

        writer.writeheader()

        for issue in issues:
            writer.writerow({
                "issue_id": issue.get("id", ""),
                "title": issue.get("title", ""),
                "true_is_bug": "",
                "true_category": "",
                "true_testable": "",
                "review_notes": "",
            })


# ==========================================
# 11. 人工標註結果比較
# ==========================================

def evaluate_results(results):
    if not GROUND_TRUTH_FILE.exists():
        print("\n找不到人工標準答案檔案")
        return

    with open(
        GROUND_TRUTH_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        reader = csv.DictReader(f)

        # 清除欄位名稱前後的空白
        fieldnames = [
            name.strip() if name else ""
            for name in (reader.fieldnames or [])
        ]

        if "issue_id" not in fieldnames:
            print("\n人工標準答案 CSV 欄位錯誤")
            print("目前讀到的欄位：", fieldnames)
            print("請確認第一行包含 issue_id")
            return

        truth_rows = []

        for row in reader:
            clean_row = {
                (key.strip() if key else ""): value
                for key, value in row.items()
            }
            truth_rows.append(clean_row)

    truth_map = {}

    for row in truth_rows:
        issue_id = str(row.get("issue_id") or "").strip()

        if issue_id:
            truth_map[issue_id] = row

    comparisons = []

    labeled_count = 0
    decided_count = 0
    uncertain_count = 0
    correct_count = 0

    for row in results:
        issue_id = str(row.get("issue_id") or "").strip()
        truth = truth_map.get(issue_id)

        if truth is None:
            continue

        label = str(
            truth.get("true_is_bug") or ""
        ).strip().lower()

        # 尚未人工標註，不納入評估
        if label not in {"true", "false"}:
            continue

        labeled_count += 1
        expected = label == "true"

        predicted = row.get("is_bug")

        # 模型沒有做出 True / False 判斷
        if type(predicted) is not bool:
            uncertain_count += 1

            comparisons.append({
                "issue_id": issue_id,
                "predicted_is_bug": "UNCERTAIN",
                "true_is_bug": expected,
                "correct": "",
                "review_status": row.get(
                    "review_status", ""
                ),
            })
            continue

        decided_count += 1
        is_correct = predicted == expected

        if is_correct:
            correct_count += 1

        comparisons.append({
            "issue_id": issue_id,
            "predicted_is_bug": predicted,
            "true_is_bug": expected,
            "correct": is_correct,
            "review_status": row.get(
                "review_status", ""
            ),
        })

    # 輸出評估結果
    with open(
        EVALUATION_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_id",
                "predicted_is_bug",
                "true_is_bug",
                "correct",
                "review_status",
            ],
        )
        writer.writeheader()
        writer.writerows(comparisons)

    print("\n========== 人工標準答案比較 ==========")
    print(f"人工已標註：{labeled_count}")
    print(f"模型有做出判斷：{decided_count}")
    print(f"模型未決定：{uncertain_count}")

    if labeled_count > 0:
        coverage = decided_count / labeled_count
        print(f"模型判斷覆蓋率：{coverage:.2%}")
    else:
        print("目前沒有已標註的人工標準答案")

    if decided_count > 0:
        accuracy = correct_count / decided_count
        print(f"判斷正確：{correct_count}")
        print(f"已決定案例準確率：{accuracy:.2%}")
    else:
        print("已決定案例準確率：無法計算")
        print("原因：模型沒有做出任何 True/False 判斷")

    print(f"評估報表：{EVALUATION_FILE}")
    print("=====================================")



# ==========================================
# 12. 主程式
# ==========================================
def main():
    issues = load_issues()

    if TEST_MODE:
        issue_map = {
            str(issue.get("id")): issue
            for issue in issues
        }

        selected_issues = [
            issue_map[issue_id]
            for issue_id in TEST_ISSUE_IDS
            if issue_id in issue_map
        ]
    else:
        selected_issues = issues

    create_ground_truth_template(selected_issues)

    print("=" * 55)
    print("GitHub Issues LLM 分類系統 V5")
    print("=" * 55)
    print(f"資料總數：{len(issues)}")
    print(f"本次處理：{len(selected_issues)}")
    print(f"模型：{MODEL}")

    results = []

    for index, issue in enumerate(
        selected_issues,
        start=1,
    ):
        issue_id = str(issue.get("id") or "")
        title = str(issue.get("title") or "")

        print("\n" + "-" * 55)
        print(
            f"[{index}/{len(selected_issues)}] "
            f"{issue_id}"
        )
        print(f"標題：{title}")

        start = time.perf_counter()

        row = {
            "issue_id": issue_id,
            "title": title,
            "url": issue.get("url", ""),
            "is_bug": None,
            "category": "other",
            "testable": None,
            "test_type": "unknown",
            "reason": "",
            "suggested_test": "Not applicable",
            "review_status": "PENDING",
            "model": MODEL,
            "status": "FAILED",
            "attempts": 0,
            "duration_seconds": 0,
            "error_message": "",
        }

        try:
            result, status, attempts = classify_issue(
                issue
            )

            row.update(result)
            row["status"] = status
            row["attempts"] = attempts

            print(f"狀態：{status}")
            print(f"疑似 Bug：{row['is_bug']}")
            print(f"類別：{row['category']}")
            print(f"UI 候選：{row['testable']}")
            print(f"測試類型：{row['test_type']}")
            print(f"審查狀態：{row['review_status']}")

        except Exception as error:
            row["error_message"] = str(error)
            row["review_status"] = "NEEDS_REVIEW"

            print(f"分類失敗：{error}")

        row["duration_seconds"] = round(
            time.perf_counter() - start,
            2,
        )

        results.append(row)
        save_results(results)

    # ======================================
    # 13. 統計
    # ======================================
    success = sum(
        r["status"] == "SUCCESS"
        for r in results
    )

    filtered = sum(
        r["status"] == "FILTERED"
        for r in results
    )

    failed = sum(
        r["status"] == "FAILED"
        for r in results
    )

    bugs = sum(
        r["is_bug"] is True
        for r in results
    )

    ui_candidates = sum(
        r["testable"] is True
        and r["test_type"] == "android_ui"
        for r in results
    )

    needs_review = sum(
        r["review_status"] == "NEEDS_REVIEW"
        for r in results
    )

    categories = {}

    for row in results:
        if row["is_bug"] is True:
            name = row["category"]
            categories[name] = (
                categories.get(name, 0) + 1
            )

    print("\n" + "=" * 55)
    print("GitHub Issues V5 分類完成")
    print("=" * 55)

    print(f"LLM 分類成功：{success}")
    print(f"資料品質過濾：{filtered}")
    print(f"分類失敗：{failed}")
    print(f"判定疑似 Bug：{bugs}")
    print(f"Android UI 測試候選：{ui_candidates}")
    print(f"需要人工審查：{needs_review}")

    print("\nBug 類別統計：")

    for category, count in sorted(
        categories.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"{category}：{count}")

    print("\n分類報表：")
    print(OUTPUT_FILE)

    print("\n人工標準答案：")
    print(GROUND_TRUTH_FILE)

    evaluate_results(results)


if __name__ == "__main__":
    main()
