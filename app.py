
# -*- coding: utf-8 -*-

# ============================================================
# Todo Web Application
# LLM 自動化測試專題
#
# 功能：
# 1. Todo 任務新增、編輯、刪除、完成
# 2. All / Active / Completed 篩選
# 3. NORMAL / BUG MODE 切換
# 4. B01 ~ B30 Bug 植入
# 5. Selenium 測試資料重設 API
# ============================================================

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    abort
)

app = Flask(__name__)

# ============================================================
# 1. 全域設定
# ============================================================

BUG_MODE = False

tasks = []
next_task_id = 1

# B27 專用狀態
b27_pending = False
b27_first_view = False


# ============================================================
# 2. 任務查詢工具
# ============================================================

def find_task(task_id):

    for task in tasks:
        if task["id"] == task_id:
            return task

    return None


def reset_all_data():

    global tasks
    global next_task_id
    global b27_pending
    global b27_first_view

    tasks = []
    next_task_id = 1

    b27_pending = False
    b27_first_view = False


# ============================================================
# 3. 首頁與任務篩選
# ============================================================

@app.route("/", methods=["GET"])
def index():

    global b27_pending
    global b27_first_view
    global tasks

    filter_type = request.args.get(
        "filter", "all"
    ).lower()

    if filter_type not in (
        "all",
        "active",
        "completed"
    ):
        filter_type = "all"

    # B27：重新整理後任務消失
    if BUG_MODE and b27_pending:

        if b27_first_view:
            b27_first_view = False

        else:
            tasks = [
                task for task in tasks
                if not task["title"].startswith("B27_")
            ]

            b27_pending = False

    # B26：切換 Active 篩選時，
    # 錯誤地將任務改成已完成
    if BUG_MODE and filter_type == "active":

        for task in tasks:

            if task["title"].startswith("B26_"):
                task["completed"] = True

    # 一般篩選
    if filter_type == "active":

        visible_tasks = [
            task for task in tasks
            if not task["completed"]
        ]

    elif filter_type == "completed":

        visible_tasks = [
            task for task in tasks
            if task["completed"]
        ]

    else:

        visible_tasks = list(tasks)

    # B05：Active 篩選錯誤隱藏任務
    if BUG_MODE and filter_type == "active":

        visible_tasks = [
            task for task in visible_tasks
            if not task["title"].startswith("B05_")
        ]

    # B06：Completed 篩選錯誤隱藏任務
    if BUG_MODE and filter_type == "completed":

        visible_tasks = [
            task for task in visible_tasks
            if not task["title"].startswith("B06_")
        ]

    # B23：Active 篩選錯誤顯示已完成任務
    if BUG_MODE and filter_type == "active":

        for task in tasks:

            if (
                task["title"].startswith("B23_")
                and task["completed"]
                and task not in visible_tasks
            ):
                visible_tasks.append(task)

    # B24：Completed 篩選錯誤顯示未完成任務
    if BUG_MODE and filter_type == "completed":

        for task in tasks:

            if (
                task["title"].startswith("B24_")
                and not task["completed"]
                and task not in visible_tasks
            ):
                visible_tasks.append(task)

    # B25：All 篩選錯誤隱藏任務
    if BUG_MODE and filter_type == "all":

        visible_tasks = [
            task for task in visible_tasks
            if not task["title"].startswith("B25_")
        ]

    return render_template(
        "index.html",
        tasks=visible_tasks,
        filter_type=filter_type
    )


# ============================================================
# 4. 新增任務
# ============================================================

@app.route("/add", methods=["POST"])
def add_task():

    global next_task_id
    global b27_pending
    global b27_first_view

    title = request.form.get(
        "title", ""
    )

    # B10：新增特定任務時 HTTP 500
    if (
        BUG_MODE
        and title.startswith("B10_CRASH_")
    ):
        abort(500)

    # NORMAL：不允許空白任務
    # B01：BUG 模式錯誤接受空白任務
    if not title.strip():

        if not BUG_MODE:
            return redirect(url_for("index"))

    # B12：新增時遺失特殊字元
    if (
        BUG_MODE
        and title.startswith("B12_")
    ):

        for character in "@#$%":
            title = title.replace(character, "")

    # B13：任務名稱遭截斷
    if (
        BUG_MODE
        and title.startswith("B13_")
    ):
        title = title[:20]

    # B14：前後空白遭刪除
    if (
        BUG_MODE
        and title.strip().startswith("B14_")
    ):
        title = title.strip()

    # B30：任務名稱被錯誤修改
    if (
        BUG_MODE
        and title.startswith("B30_")
    ):
        title = "B30_WRONG_TITLE"

    task = {
        "id": next_task_id,
        "title": title,
        "completed": False
    }

    tasks.append(task)
    next_task_id += 1

    # B11：新增時重複建立任務
    if (
        BUG_MODE
        and title.startswith("B11_")
    ):

        duplicate_task = {
            "id": next_task_id,
            "title": title,
            "completed": False
        }

        tasks.append(duplicate_task)
        next_task_id += 1

    # B27：下一次重新開啟首頁時，
    # 錯誤刪除任務
    if (
        BUG_MODE
        and title.startswith("B27_")
    ):

        b27_pending = True
        b27_first_view = True

    return redirect(url_for("index"))


# ============================================================
# 5. 任務詳細頁
# ============================================================

@app.route("/task/<int:task_id>", methods=["GET"])
def task_detail(task_id):

    task = find_task(task_id)

    if task is None:
        abort(404)

    display_task = task.copy()

    # B09：詳細頁顯示錯誤任務名稱
    if (
        BUG_MODE
        and task["title"].startswith("B09_")
    ):
        display_task["title"] = "WRONG_TASK_DATA"

    # B28：詳細頁完成狀態顯示相反
    if (
        BUG_MODE
        and task["title"].startswith("B28_")
    ):
        display_task["completed"] = (
            not task["completed"]
        )

    return render_template(
        "detail.html",
        task=display_task
    )


# ============================================================
# 6. 編輯任務
# ============================================================

@app.route(
    "/edit/<int:task_id>",
    methods=["GET", "POST"]
)
def edit_task(task_id):

    global next_task_id

    task = find_task(task_id)

    if task is None:
        abort(404)

    if request.method == "GET":

        return render_template(
            "edit.html",
            task=task
        )

    new_title = request.form.get(
        "title", ""
    )

    original_title = task["title"]

    # B02：編輯後沒有儲存
    if (
        BUG_MODE
        and original_title.startswith("B02_")
    ):
        return redirect(url_for("index"))

    # B17：錯誤接受空白編輯
    if not new_title.strip():

        if not (
            BUG_MODE
            and original_title.startswith("B17_")
        ):
            return redirect(url_for("index"))

    # B16：編輯後遺失特殊字元
    if (
        BUG_MODE
        and original_title.startswith("B16_")
    ):

        for character in "@#$%":
            new_title = new_title.replace(
                character, ""
            )

    # B15：編輯時額外建立重複任務
    if (
        BUG_MODE
        and original_title.startswith("B15_")
    ):

        duplicate_task = {
            "id": next_task_id,
            "title": original_title,
            "completed": task["completed"]
        }

        tasks.append(duplicate_task)
        next_task_id += 1

    # B18：編輯後完成狀態重設
    if (
        BUG_MODE
        and original_title.startswith("B18_")
    ):
        task["completed"] = False

    task["title"] = new_title

    return redirect(url_for("index"))


# ============================================================
# 7. 完成 / 取消完成
# ============================================================

@app.route(
    "/toggle/<int:task_id>",
    methods=["POST"]
)
def toggle_task(task_id):

    task = find_task(task_id)

    if task is None:
        abort(404)

    original_completed = task["completed"]

    # B04：無法標記完成
    if (
        BUG_MODE
        and task["title"].startswith("B04_")
        and not original_completed
    ):
        return redirect(url_for("index"))

    # B07：無法取消完成
    if (
        BUG_MODE
        and task["title"].startswith("B07_")
        and original_completed
    ):
        return redirect(url_for("index"))

    task["completed"] = not original_completed

    # B21：修改一個任務時，
    # 其他任務狀態也被修改
    if (
        BUG_MODE
        and task["title"].startswith("B21_")
    ):

        for other_task in tasks:

            if other_task["id"] != task_id:

                other_task["completed"] = (
                    task["completed"]
                )

    # B22：取消完成時任務名稱被修改
    if (
        BUG_MODE
        and task["title"].startswith("B22_")
        and original_completed
    ):
        task["title"] = "B22_WRONG_TITLE"

    return redirect(url_for("index"))


# ============================================================
# 8. 刪除任務
# ============================================================

@app.route(
    "/delete/<int:task_id>",
    methods=["POST"]
)
def delete_task(task_id):

    global tasks

    task = find_task(task_id)

    if task is None:
        abort(404)

    # B03：無法刪除任務
    if (
        BUG_MODE
        and task["title"].startswith("B03_")
    ):
        return redirect(url_for("index"))

    # B20：無法刪除已完成任務
    if (
        BUG_MODE
        and task["title"].startswith("B20_")
        and task["completed"]
    ):
        return redirect(url_for("index"))

    # B19：刪除錯誤任務
    if (
        BUG_MODE
        and task["title"].startswith("B19_")
    ):

        for other_task in tasks:

            if other_task["id"] != task_id:

                tasks = [
                    item for item in tasks
                    if item["id"] != other_task["id"]
                ]

                return redirect(url_for("index"))

    tasks = [
        item for item in tasks
        if item["id"] != task_id
    ]

    return redirect(url_for("index"))


# ============================================================
# 9. 清除已完成任務
# ============================================================

@app.route(
    "/clear-completed",
    methods=["POST"]
)
def clear_completed():

    global tasks

    # B29：錯誤刪除未完成任務
    if BUG_MODE:

        b29_tasks = [
            task for task in tasks
            if task["title"].startswith("B29_")
        ]

        if b29_tasks:

            tasks = [
                task for task in tasks
                if (
                    not task["title"].startswith("B29_")
                    or task["completed"]
                )
            ]

            return redirect(url_for("index"))

    # B08：無法清除指定已完成任務
    if BUG_MODE:

        tasks = [
            task for task in tasks
            if (
                not task["completed"]
                or task["title"].startswith("B08_")
            )
        ]

    else:

        tasks = [
            task for task in tasks
            if not task["completed"]
        ]

    return redirect(url_for("index"))


# ============================================================
# 10. 重設測試資料
# ============================================================

@app.route(
    "/test/reset",
    methods=["POST"]
)
def test_reset():

    reset_all_data()

    return jsonify({
        "status": "ok",
        "message": "測試資料已重設",
        "mode": (
            "BUG" if BUG_MODE else "NORMAL"
        )
    })


# ============================================================
# 11. 查詢 / 切換測試模式
# ============================================================

@app.route(
    "/test/mode",
    methods=["GET", "POST"]
)
def test_mode():

    global BUG_MODE

    # GET：查詢目前模式
    if request.method == "GET":

        return jsonify({
            "bug_mode": BUG_MODE,
            "mode": (
                "BUG" if BUG_MODE else "NORMAL"
            )
        })

    # POST：切換測試模式
    data = request.get_json(
        silent=True
    )

    if not isinstance(data, dict):

        return jsonify({
            "status": "error",
            "message": "請提供 JSON 資料"
        }), 400

    mode = str(
        data.get("mode", "")
    ).strip().lower()

    if mode not in (
        "normal",
        "bug"
    ):

        return jsonify({
            "status": "error",
            "message": "mode 必須是 normal 或 bug"
        }), 400

    # 切換模式
    BUG_MODE = (
        mode == "bug"
    )

    # 避免不同模式共用測試資料
    reset_all_data()

    return jsonify({
        "status": "ok",
        "bug_mode": BUG_MODE,
        "mode": (
            "BUG" if BUG_MODE else "NORMAL"
        ),
        "message": "測試模式切換成功"
    })


# ============================================================
# 12. 啟動 Flask
# ============================================================

if __name__ == "__main__":

    print("=" * 55)
    print("Todo Web Application")
    print("=" * 55)

    print(
        "目前模式：",
        "BUG MODE" if BUG_MODE else "NORMAL MODE"
    )

    print(
        "URL：http://127.0.0.1:5000"
    )

    print("=" * 55)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )
