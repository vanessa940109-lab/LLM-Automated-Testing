
# -*- coding: utf-8 -*-

# ============================================================
# LLM Web Test Planner - B01 ~ B30
#
# 功能：
# 1. 使用 Ollama qwen2.5:3b 產生 JSON
# 2. 支援 B01 ~ B30 測試案例
# 3. 驗證 JSON 格式、操作流程及輸入值
# 4. 失敗最多重試 3 次
# 5. 自動跳過已存在的 JSON
# 6. 儲存 Planner CSV 紀錄
#
# 目前設定：
# 自動產生所有缺少的 JSON Test Plan
# ============================================================

import csv
import json
import re
import time
import urllib.error
import urllib.request

from datetime import datetime
from pathlib import Path


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_NAME = "qwen2.5:3b"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

BUG_CASES_FILE = BASE_DIR / "bug_cases.json"

OUTPUT_DIR = BASE_DIR / "generated_plans"

RESULT_DIR = BASE_DIR / "planner_results"

MAX_RETRIES = 3

OLLAMA_TIMEOUT = 180

# None：檢查 B01 ~ B30，產生缺少的 JSON
SELECTED_BUG_IDS = None

# False：保留已存在的 JSON
OVERWRITE_EXISTING = False

VALID_BUG_IDS = {
    f"B{i:02d}" for i in range(1, 31)
}


# ============================================================
# 2. B01 ~ B10 固定測試資料
# ============================================================

TEST_TITLES = {
    "B01": "   ",
    "B02": "B02_TEST",
    "B03": "B03_TEST",
    "B04": "B04_TEST",
    "B05": "B05_TEST",
    "B06": "B06_TEST",
    "B07": "B07_TEST",
    "B08": "B08_TEST",
    "B09": "B09_TEST",
    "B10": "B10_CRASH_TEST"
}

EDITED_TITLE = "B02_EDITED"


# ============================================================
# 3. 網頁元素
# ============================================================

ELEMENTS = {
    "title": "id",
    "add-task": "id",
    "task-checkbox": "class",
    "task-title": "class",
    "edit-link": "class",
    "delete-button": "class",
    "filter-all": "id",
    "filter-active": "id",
    "filter-completed": "id",
    "clear-completed": "id",
    "edit-title": "id",
    "save-edit": "id"
}

ALLOWED_ACTIONS = {
    "open",
    "input",
    "click",
    "check",
    "uncheck"
}


# ============================================================
# 4. B01 ~ B10 固定操作流程
# ============================================================

REQUIRED_FLOWS = {
    "B01": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task")
    ],
    "B02": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("click", "edit-link"),
        ("input", "edit-title"),
        ("click", "save-edit")
    ],
    "B03": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("click", "delete-button")
    ],
    "B04": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("check", "task-checkbox")
    ],
    "B05": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("click", "filter-active")
    ],
    "B06": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("check", "task-checkbox"),
        ("click", "filter-completed")
    ],
    "B07": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("check", "task-checkbox"),
        ("uncheck", "task-checkbox")
    ],
    "B08": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("check", "task-checkbox"),
        ("click", "clear-completed")
    ],
    "B09": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task"),
        ("click", "task-title")
    ],
    "B10": [
        ("open", "/"),
        ("input", "title"),
        ("click", "add-task")
    ]
}


# ============================================================
# 5. 讀取 Bug Cases
# ============================================================

def load_bug_cases():

    with BUG_CASES_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        bugs = json.load(file)

    if not isinstance(bugs, list):
        raise ValueError(
            "bug_cases.json 必須是 JSON 陣列"
        )

    for bug in bugs:

        if not isinstance(bug, dict):
            raise ValueError(
                "Bug Case 必須是 JSON Object"
            )

        for field in ("id", "title", "description"):

            if field not in bug:
                raise ValueError(
                    f"Bug Case 缺少 {field}"
                )

    return bugs


# ============================================================
# 6. 取得案例設定
# ============================================================

def get_case_config(bug):

    bug_id = bug["id"]

    if bug_id not in VALID_BUG_IDS:
        raise ValueError(
            f"不支援的 Bug ID：{bug_id}"
        )

    elements = ELEMENTS.copy()

    if bug_id in REQUIRED_FLOWS:

        flow = REQUIRED_FLOWS[bug_id]

        test_title = TEST_TITLES[bug_id]

        input_values = {
            "title": test_title
        }

        if bug_id == "B02":
            input_values["edit-title"] = EDITED_TITLE

    else:

        test_title = bug.get("test_title")

        required_flow = bug.get("required_flow")

        extra_elements = bug.get("elements", {})

        input_values = bug.get("input_values", {})

        if not isinstance(test_title, str):
            raise ValueError(
                f"{bug_id} 缺少 test_title"
            )

        if not isinstance(required_flow, list) or not required_flow:
            raise ValueError(
                f"{bug_id} 缺少 required_flow"
            )

        if not isinstance(extra_elements, dict):
            raise ValueError(
                f"{bug_id} elements 格式錯誤"
            )

        if not isinstance(input_values, dict):
            raise ValueError(
                f"{bug_id} input_values 格式錯誤"
            )

        for target, locator in extra_elements.items():

            if locator not in (
                "id",
                "class",
                "css",
                "name"
            ):
                raise ValueError(
                    f"不支援 locator：{locator}"
                )

            elements[target] = locator

        flow = []

        for step in required_flow:

            if not isinstance(step, dict):
                raise ValueError(
                    f"{bug_id} required_flow 格式錯誤"
                )

            flow.append((
                step.get("action"),
                step.get("target")
            ))

        input_values = input_values.copy()

        input_values["title"] = test_title

    for action, target in flow:

        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"{bug_id} 不支援 action：{action}"
            )

        if action == "open":

            if target != "/":
                raise ValueError(
                    "open 只能使用 /"
                )

        elif target not in elements:

            raise ValueError(
                f"{bug_id} 未定義元素：{target}"
            )

        if action == "input":

            if target not in input_values:
                raise ValueError(
                    f"{bug_id} 缺少輸入值：{target}"
                )

        if action in ("check", "uncheck"):

            if target != "task-checkbox":
                raise ValueError(
                    "check/uncheck 只能操作 task-checkbox"
                )

    return {
        "bug_id": bug_id,
        "title": test_title,
        "flow": flow,
        "elements": elements,
        "input_values": input_values,
        "input_targets": set(input_values.keys())
    }


# ============================================================
# 7. 清理 LLM 回應
# ============================================================

def clean_response(text):

    text = re.sub(
        r"\x1b\[[0-?]*[ -/]*[@-~]",
        "",
        text
    )

    text = "".join(
        char
        for char in text
        if ord(char) >= 32
        or char in "\n\r\t"
    )

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    return text.strip()


# ============================================================
# 8. 建立 LLM Prompt
# ============================================================

def build_prompt(bug, retry_reason=None):

    config = get_case_config(bug)

    bug_id = config["bug_id"]

    flow = config["flow"]

    elements = config["elements"]

    input_values = config["input_values"]

    flow_text = "\n".join(
        f"{index}. {action} {target}"
        for index, (action, target) in enumerate(
            flow,
            start=1
        )
    )

    locator_text = json.dumps(
        elements,
        ensure_ascii=False,
        indent=2
    )

    input_text = json.dumps(
        input_values,
        ensure_ascii=False,
        indent=2
    )

    retry_text = ""

    if retry_reason:

        retry_text = (
            "\nPREVIOUS OUTPUT INVALID:\n"
            + retry_reason
            + "\nPlease correct the error.\n"
        )

    return f"""
You are an automated web UI test planner.

Generate a valid executable JSON Test Plan
for a Todo Web application.

BUG INFORMATION:

Bug ID: {bug_id}
Title: {bug["title"]}
Description: {bug["description"]}

REQUIRED TEST FLOW:

{flow_text}

Follow the exact order.
Do not skip or add steps.

REQUIRED INPUT VALUES:

{input_text}

Use the exact input values.
Preserve whitespace and special characters.

LOCATOR MAPPING:

{locator_text}

ALLOWED ACTIONS:

open
input
click
check
uncheck

RULES:

1. Return ONLY valid JSON.
2. Do not include Markdown.
3. Follow the required flow exactly.
4. Use the correct locator.
5. open must use target "/".
6. preconditions must be [].
7. expected_result describes CORRECT behavior.
8. Do not add unnecessary steps.
9. Use category "todo_web".
10. Every input step must include its value.
11. check/uncheck only supports task-checkbox.
12. Use model "{MODEL_NAME}".
13. Do not change any required input value.

{retry_text}

OUTPUT FORMAT:

{{
  "bug_id": "{bug_id}",
  "category": "todo_web",
  "model": "{MODEL_NAME}",
  "test_name": "Test {bug_id}",
  "preconditions": [],
  "steps": [
    {{
      "action": "open",
      "target": "/"
    }}
  ],
  "expected_result": {{
    "type": "description",
    "value": "Describe the correct expected behavior."
  }}
}}

The steps above are an example only.
Generate ALL steps from REQUIRED TEST FLOW.

Return JSON only.
"""


# ============================================================
# 9. 呼叫 Ollama API
# ============================================================

def call_ollama(prompt):

    print(f"正在呼叫 Ollama：{MODEL_NAME}")

    payload = json.dumps({
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0
        }
    }).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=OLLAMA_TIMEOUT
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        detail = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"Ollama HTTP {error.code}：{detail}"
        ) from error

    except urllib.error.URLError as error:

        raise RuntimeError(
            f"無法連線 Ollama：{error}"
        ) from error

    except TimeoutError as error:

        raise RuntimeError(
            f"Ollama 超過 {OLLAMA_TIMEOUT} 秒"
        ) from error

    if not isinstance(result, dict):
        raise RuntimeError(
            "Ollama 回應格式錯誤"
        )

    if result.get("error"):
        raise RuntimeError(
            f"Ollama 錯誤：{result['error']}"
        )

    response_text = clean_response(
        result.get("response", "")
    )

    if not response_text:
        raise RuntimeError(
            "Ollama 回傳空白內容"
        )

    return response_text


# ============================================================
# 10. 驗證 JSON 基本結構
# ============================================================

def validate_basic_structure(plan):

    if not isinstance(plan, dict):
        return False, "Plan 必須是 JSON Object"

    required_fields = [
        "bug_id",
        "category",
        "test_name",
        "preconditions",
        "steps",
        "expected_result"
    ]

    for field in required_fields:

        if field not in plan:
            return False, f"缺少欄位：{field}"

    if not isinstance(plan["bug_id"], str):
        return False, "bug_id 必須是字串"

    if plan["category"] != "todo_web":
        return False, "category 必須是 todo_web"

    if not isinstance(plan["test_name"], str):
        return False, "test_name 必須是字串"

    if plan["preconditions"] != []:
        return False, "preconditions 必須是 []"

    if not isinstance(plan["steps"], list):
        return False, "steps 必須是 list"

    if not plan["steps"]:
        return False, "steps 不可以為空"

    expected = plan["expected_result"]

    if not isinstance(expected, dict):
        return False, "expected_result 必須是 Object"

    if expected.get("type") != "description":
        return False, (
            "expected_result.type 必須是 description"
        )

    if not isinstance(expected.get("value"), str):
        return False, (
            "expected_result.value 必須是字串"
        )

    if not expected["value"].strip():
        return False, (
            "expected_result 不可以為空"
        )

    if "model" in plan:

        if not isinstance(plan["model"], str):
            return False, "model 必須是字串"

    return True, "OK"


# ============================================================
# 11. 驗證 Test Plan
# ============================================================

def validate_bug_plan(bug, plan):

    valid, reason = validate_basic_structure(plan)

    if not valid:
        return False, reason

    config = get_case_config(bug)

    bug_id = config["bug_id"]

    if plan["bug_id"] != bug_id:
        return False, "bug_id 不符合"

    expected_flow = config["flow"]

    elements = config["elements"]

    input_values = config["input_values"]

    input_targets = config["input_targets"]

    actual_flow = []

    for index, step in enumerate(
        plan["steps"],
        start=1
    ):

        if not isinstance(step, dict):
            return False, (
                f"Step {index} 格式錯誤"
            )

        action = step.get("action")
        target = step.get("target")

        if action not in ALLOWED_ACTIONS:
            return False, (
                f"Step {index} action 錯誤"
            )

        actual_flow.append(
            (action, target)
        )

        if action == "open":

            if target != "/":
                return False, (
                    "open 只能使用 /"
                )

            continue

        if target not in elements:
            return False, (
                f"不支援 target：{target}"
            )

        expected_locator = elements[target]

        locator = step.get(
            "locator",
            expected_locator
        )

        if locator != expected_locator:
            return False, (
                f"{target} locator 錯誤"
            )

        if action == "input":

            if target not in input_targets:
                return False, (
                    f"不能輸入 {target}"
                )

            if not isinstance(step.get("value"), str):
                return False, (
                    f"{target} 缺少 value"
                )

            required_value = input_values.get(
                target
            )

            if step["value"] != required_value:
                return False, (
                    f"{target} value 必須是 "
                    f"{repr(required_value)}"
                )

        if action in ("check", "uncheck"):

            if target != "task-checkbox":
                return False, (
                    "checkbox 操作錯誤"
                )

        if action == "click":

            if target in input_targets:
                return False, (
                    "不能 click 輸入框"
                )

    if actual_flow != expected_flow:

        return False, (
            f"{bug_id} 操作流程錯誤。"
            f"預期：{expected_flow}；"
            f"實際：{actual_flow}"
        )

    return True, "PLAN_VALID"


# ============================================================
# 12. 儲存 JSON Test Plan
# ============================================================

def save_plan(plan):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path = OUTPUT_DIR / f"{plan['bug_id']}.json"

    if path.exists() and not OVERWRITE_EXISTING:
        raise FileExistsError(
            f"檔案已存在，不覆蓋：{path}"
        )

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            plan,
            file,
            ensure_ascii=False,
            indent=4
        )

    return path


# ============================================================
# 13. 產生單一 Test Plan
# ============================================================

def generate_plan(bug):

    bug_id = bug["id"]

    print()
    print("=" * 60)
    print(f"正在處理：{bug_id}")
    print("=" * 60)

    start = time.perf_counter()

    attempts = 0
    last_error = ""
    status = "PLAN_INVALID"

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    plan_path = OUTPUT_DIR / f"{bug_id}.json"

    # 已存在就跳過
    if plan_path.exists() and not OVERWRITE_EXISTING:

        print(f"已存在，跳過：{plan_path}")

        return {
            "bug_id": bug_id,
            "model": MODEL_NAME,
            "status": "SKIPPED_EXISTING",
            "attempts": 0,
            "duration_seconds": 0,
            "error_message": ""
        }

    # 檢查 Bug Case
    try:

        get_case_config(bug)

    except Exception as error:

        return {
            "bug_id": bug_id,
            "model": MODEL_NAME,
            "status": "CONFIG_ERROR",
            "attempts": 0,
            "duration_seconds": 0,
            "error_message": str(error)
        }

    # 呼叫 LLM
    for attempt in range(1, MAX_RETRIES + 1):

        attempts = attempt

        print(
            f"Generation Attempt："
            f"{attempt}/{MAX_RETRIES}"
        )

        prompt = build_prompt(
            bug,
            last_error if attempt > 1 else None
        )

        try:

            response = call_ollama(prompt)

            plan = json.loads(
                response,
                strict=False
            )

            valid, reason = validate_bug_plan(
                bug,
                plan
            )

            if not valid:

                last_error = reason

                print(
                    f"PLAN_INVALID：{reason}"
                )

                continue

            plan["model"] = MODEL_NAME

            path = save_plan(plan)

            status = "PLAN_VALID"
            last_error = ""

            print("PLAN_VALID")
            print(f"儲存成功：{path}")

            break

        except Exception as error:

            last_error = str(error)

            print(f"產生失敗：{last_error}")

    duration = round(
        time.perf_counter() - start,
        2
    )

    return {
        "bug_id": bug_id,
        "model": MODEL_NAME,
        "status": status,
        "attempts": attempts,
        "duration_seconds": duration,
        "error_message": last_error
    }


# ============================================================
# 14. 儲存 CSV
# ============================================================

def save_results(results):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    result_file = (
        RESULT_DIR
        / f"planner_results_{timestamp}.csv"
    )

    fields = [
        "bug_id",
        "model",
        "status",
        "attempts",
        "duration_seconds",
        "error_message"
    ]

    with result_file.open(
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

    return result_file


# ============================================================
# 15. 主程式
# ============================================================

def main():

    print()
    print("=" * 60)
    print("LLM Web Test Planner")
    print(f"Model：{MODEL_NAME}")
    print("=" * 60)

    bugs = load_bug_cases()

    bugs = [
        bug
        for bug in bugs
        if bug["id"] in VALID_BUG_IDS
    ]

    if SELECTED_BUG_IDS is not None:

        bugs = [
            bug
            for bug in bugs
            if bug["id"] in SELECTED_BUG_IDS
        ]

    print(f"案例數量：{len(bugs)}")

    results = []

    for bug in bugs:

        result = generate_plan(bug)

        results.append(result)

    result_file = save_results(results)

    valid_count = sum(
        result["status"] == "PLAN_VALID"
        for result in results
    )

    skipped_count = sum(
        result["status"] == "SKIPPED_EXISTING"
        for result in results
    )

    error_count = sum(
        result["status"] in (
            "PLAN_INVALID",
            "CONFIG_ERROR"
        )
        for result in results
    )

    print()
    print("=" * 60)
    print("LLM Test Plan Generation Summary")
    print("=" * 60)

    print(f"案例總數：{len(results)}")
    print(f"新產生有效計畫：{valid_count}")
    print(f"既有計畫跳過：{skipped_count}")
    print(f"失敗或設定錯誤：{error_count}")
    print(f"實驗紀錄：{result_file}")

    print("=" * 60)


if __name__ == "__main__":
    main()
