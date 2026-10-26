
# -*- coding: utf-8 -*-

# ============================================================
# Dashboard Batch Runner
# LLM 自動化測試專題
#
# 功能：
# 1. 批次執行 B01 ~ B30
# 2. 每個案例重複測試 1 / 3 / 5 / 10 次
# 3. 呼叫 dashboard_runner.py
# 4. 保留每次測試的 CSV
# 5. 產生批次彙整 CSV
# 6. 統計 PASS / BUG_REPRODUCED / ERROR
# 7. 記錄模型、Test Plan 驗證及執行時間
# 8. 單筆錯誤不會中斷整批測試
# ============================================================

import csv
import uuid

from datetime import datetime
from pathlib import Path

from dashboard_runner import run_dashboard_test


# ============================================================
# 1. 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

BATCH_RESULT_DIR = BASE_DIR / "batch_results"

PLAN_DIR = BASE_DIR / "generated_plans"

BUG_IDS = [
    f"B{i:02d}" for i in range(1, 31)
]

VALID_REPEAT_COUNTS = (1, 3, 5, 10)

CSV_FIELDS = [
    "batch_id",
    "run_id",
    "timestamp",
    "bug_id",
    "repeat_index",
    "model",
    "mode",
    "plan_valid",
    "test_result",
    "duration_seconds",
    "error_message",
    "result_file"
]


# ============================================================
# 2. 儲存批次 CSV
# ============================================================

def save_batch_csv(records, result_file):

    BATCH_RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with result_file.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS
        )

        writer.writeheader()
        writer.writerows(records)


# ============================================================
# 3. 建立單筆錯誤紀錄
# ============================================================

def create_error_record(
    batch_id,
    bug_id,
    repeat_index,
    mode,
    timestamp,
    error
):

    return {
        "batch_id": batch_id,
        "run_id": "",
        "timestamp": timestamp,
        "bug_id": bug_id,
        "repeat_index": repeat_index,
        "model": "unknown",
        "mode": mode.upper(),
        "plan_valid": False,
        "test_result": "ERROR",
        "duration_seconds": "",
        "error_message": str(error),
        "result_file": ""
    }


# ============================================================
# 4. 執行批次測試
# ============================================================

def run_batch_test(
    mode="normal",
    repeat_count=1
):

    # --------------------------------------------------------
    # 驗證測試模式
    # --------------------------------------------------------

    if mode not in ("normal", "bug"):

        raise ValueError(
            f"不支援的測試模式：{mode}"
        )

    # --------------------------------------------------------
    # 驗證重複次數
    # --------------------------------------------------------

    if repeat_count not in VALID_REPEAT_COUNTS:

        raise ValueError(
            f"不支援的重複次數：{repeat_count}"
        )

    # --------------------------------------------------------
    # 建立批次資訊
    # --------------------------------------------------------

    batch_id = uuid.uuid4().hex[:12]

    file_timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    result_file = (
        BATCH_RESULT_DIR
        / f"batch_{mode}_{file_timestamp}.csv"
    )

    records = []

    total_tests = (
        len(BUG_IDS) * repeat_count
    )

    print()
    print("=" * 60)
    print("Dashboard Batch Selenium Test")
    print("=" * 60)

    print(f"Batch ID：{batch_id}")
    print(f"測試模式：{mode.upper()}")
    print("測試案例：B01 ~ B30")
    print(f"每個案例重複：{repeat_count} 次")
    print(f"總測試次數：{total_tests}")

    print("=" * 60)

    # --------------------------------------------------------
    # 5. 逐一執行測試
    # --------------------------------------------------------

    for bug_id in BUG_IDS:

        for repeat_index in range(
            1,
            repeat_count + 1
        ):

            print()
            print("-" * 55)

            print(
                f"執行 {bug_id} "
                f"第 {repeat_index}/{repeat_count} 次"
            )

            print("-" * 55)

            timestamp = (
                datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
                )
            )

            try:

                # --------------------------------------------
                # 確認 Test Plan 是否存在
                # --------------------------------------------

                plan_file = (
                    PLAN_DIR / f"{bug_id}.json"
                )

                if not plan_file.is_file():

                    raise FileNotFoundError(
                        f"{bug_id} 尚未產生 JSON Test Plan"
                    )

                # --------------------------------------------
                # 呼叫單次 Selenium Runner
                # --------------------------------------------

                result = run_dashboard_test(
                    bug_id=bug_id,
                    mode=mode
                )

                record = {
                    "batch_id": batch_id,

                    "run_id": result.get(
                        "run_id", ""
                    ),

                    "timestamp": timestamp,
                    "bug_id": bug_id,
                    "repeat_index": repeat_index,

                    "model": result.get(
                        "model", "unknown"
                    ),

                    "mode": mode.upper(),

                    "plan_valid": result.get(
                        "plan_valid", False
                    ),

                    "test_result": result.get(
                        "test_result", "ERROR"
                    ),

                    "duration_seconds": result.get(
                        "duration_seconds", ""
                    ),

                    "error_message": result.get(
                        "error_message", ""
                    ),

                    "result_file": result.get(
                        "result_file", ""
                    )
                }

            except Exception as error:

                # --------------------------------------------
                # 單次錯誤不影響後續案例
                # --------------------------------------------

                record = create_error_record(
                    batch_id=batch_id,
                    bug_id=bug_id,
                    repeat_index=repeat_index,
                    mode=mode,
                    timestamp=timestamp,
                    error=error
                )

                print(
                    f"執行錯誤：{error}"
                )

            # -----------------------------------------------
            # 收集結果
            # -----------------------------------------------

            records.append(record)

            print(
                f"結果：{record['test_result']}"
            )

            # -----------------------------------------------
            # 每次完成就更新 CSV
            # 避免中途停止時失去全部紀錄
            # -----------------------------------------------

            save_batch_csv(
                records,
                result_file
            )

    # ========================================================
    # 6. 統計測試結果
    # ========================================================

    pass_count = sum(
        1
        for record in records
        if record["test_result"] == "PASS"
    )

    bug_reproduced_count = sum(
        1
        for record in records
        if record["test_result"] == "BUG_REPRODUCED"
    )

    failed_count = sum(
        1
        for record in records
        if record["test_result"] not in (
            "PASS",
            "BUG_REPRODUCED"
        )
    )

    # --------------------------------------------------------
    # 平均執行時間
    # --------------------------------------------------------

    durations = []

    for record in records:

        try:

            duration = float(
                record["duration_seconds"]
            )

            durations.append(duration)

        except (
            ValueError,
            TypeError
        ):

            pass

    average_duration = (
        round(
            sum(durations) / len(durations),
            3
        )
        if durations
        else None
    )

    # --------------------------------------------------------
    # 符合預期的結果
    # --------------------------------------------------------

    expected_result = (
        "PASS"
        if mode == "normal"
        else "BUG_REPRODUCED"
    )

    expected_count = sum(
        1
        for record in records
        if (
            record["test_result"] == expected_result
            and record["plan_valid"] is True
        )
    )

    expected_rate = (
        round(
            expected_count / total_tests * 100,
            2
        )
        if total_tests > 0
        else 0
    )

    # ========================================================
    # 7. 建立統計結果
    # ========================================================

    summary = {
        "batch_id": batch_id,
        "mode": mode,

        "total_tests": total_tests,

        "pass_count": pass_count,

        "bug_reproduced_count": (
            bug_reproduced_count
        ),

        "failed_count": failed_count,

        "expected_count": expected_count,

        "expected_rate": expected_rate,

        "average_duration": average_duration,

        "result_file": str(result_file)
    }

    # ========================================================
    # 8. 顯示批次結果
    # ========================================================

    print()
    print("=" * 60)
    print("Batch Test Summary")
    print("=" * 60)

    print(f"Batch ID：{batch_id}")
    print(f"測試模式：{mode.upper()}")
    print(f"總測試次數：{total_tests}")

    print(f"PASS：{pass_count}")

    print(
        "BUG_REPRODUCED："
        f"{bug_reproduced_count}"
    )

    print(
        f"FAILED / ERROR：{failed_count}"
    )

    print(
        f"符合預期：{expected_count}"
    )

    print(
        f"符合預期比例：{expected_rate}%"
    )

    print(
        f"平均執行時間：{average_duration} 秒"
    )

    print(
        f"彙整 CSV：{result_file}"
    )

    print("=" * 60)

    return summary


# ============================================================
# 9. 單獨執行
# ============================================================

if __name__ == "__main__":

    print(
        "Dashboard Batch Runner 已載入。"
    )

    print(
        "請透過 dashboard.py "
        "選擇批次測試並執行。"
    )
