# LLM 驅動之待辦事項應用程式自動化測試生成與執行系統

## 一、專題介紹

本專題開發一套結合大型語言模型（LLM）與自動化測試工具的測試系統，透過 GitHub Issues 取得問題描述，進行 Bug 類型分類、測試計畫生成與自動化測試執行，並記錄測試結果，以協助開發者分析應用程式問題。

系統整合 Python、Ollama、Selenium、Appium 與 Flask Dashboard，支援網頁測試及 Android 應用程式測試。

## 二、系統流程

GitHub Issues → Bug 分類 → LLM 生成 JSON Test Plan → Selenium／Appium 執行測試 → 結果紀錄與 Dashboard 顯示

## 三、主要技術

- Python：系統開發及測試流程控制
- Ollama／LLM：Bug 分類及測試計畫生成
- Selenium：網頁自動化測試
- Appium／UiAutomator2：Android 自動化測試
- Flask：Dashboard 網頁管理介面
- JSON：儲存測試計畫
- CSV：儲存測試執行結果

## 四、專案檔案說明

| 檔案或資料夾 | 說明 |
| --- | --- |
| `dashboard.py` | Dashboard 主程式 |
| `templates/` | Dashboard 網頁介面 |
| `github_fetcher.py` | GitHub Issues 資料擷取 |
| `github_issue_classifier.py` | GitHub Issue 分類 |
| `github_test_planner.py` | 測試計畫生成 |
| `llm_planner.py` | LLM 測試規劃 |
| `llm_executor.py` | 測試執行相關程式 |
| `generated_plans/` | B01～B30 JSON 測試計畫 |
| `test_b01_android.py` | Android B01 測試程式 |
| `test_gh1046_verify.py` | GH-1046 測試程式 |
| `test_gh1035.py` | GH-1035 測試程式 |
| `test_gh969.py` | GH-969 測試程式 |
| `test_results/` | 測試結果、CSV 報表與證據 |

## 五、測試案例

本專題包含 B01～B30 本地 Bug 測試計畫，並針對 GitHub Issues 建立 Android 自動化測試程式。

測試案例與測試紀錄分別保存在 `generated_plans/` 及 `test_results/` 中。

## 六、測試執行紀錄

GitHub Issue 測試紀錄包含下列狀態：

| Issue ID | Bug 類型 | 測試結果 |
| --- | --- | --- |
| GH-1046 | snackbar | INCONCLUSIVE |
| GH-1035 | navigation | NOT_REPRODUCED |
| GH-969 | task_complete | SUSPECTED_UNCHECK_BUG |

以上為測試紀錄中觀察到的結果，並不代表所有 Bug 均已成功重現。

其他 Selenium 與 Android 測試資料請參考 `test_results/`。

## 七、研究成果與用途

本專題展示利用大型語言模型輔助測試規劃，並整合 Selenium 與 Appium 執行自動化測試的系統流程。測試結果可透過 Dashboard 查看，相關紀錄與測試證據亦可用於分析與後續改善。

本儲存庫提供畢業專題報告附錄之程式碼、測試案例與執行紀錄查閱。
