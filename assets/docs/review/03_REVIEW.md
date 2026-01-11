# 03_REVIEW_UNIFIED.md

## 1. Executive Summary
The implementation of **Phase 3: Core UI** generally adheres well to the architectural constraints (PyQt5, Signal-Driven MVC). The directory structure matches the standards, and the "Dumb View" pattern is respected.

However, there are several strict typing issues, missing internationalization (i18n) wrappers for hardcoded strings in the delegates, and the `AppController` logic needs significantly higher test coverage before moving to Phase 4.

## 2. Coverage Exceptions Verification
| Component | Coverage | Verdict | Reasoning |
| :--- | :--- | :--- | :--- |
| `library_item_delegate.py` | ~25% | **ACCEPTED** | Testing `QPainter` calls (e.g., `painter.drawText`) is brittle and yields low value. Visual verification (User Acceptance Testing) is standard for rendering code. |
| `app_controller.py` | ~52% | **REJECTED** | **Critical Issue.** The Controller is the "brain" of the application (Pure Logic). Logic such as "If I press Enter on a Movie -> Check State -> Trigger Download" does *not* require a rendered UI. It can and should be tested using Mocks for the View and Database. Coverage for the Controller should be >80% to ensure the State Machine logic is robust. |

---

## 3. Architecture & Standards Compliance

### 3.1. Adherence to Docs
*   **State Machine:** The `AppController` correctly implements the State Pattern defined in `04_UI_UX_STATE_MACHINE.md`.
*   **Input Manager:** Correctly implements the event filter and mapping logic defined in `01_SYSTEM_ARCHITECTURE.md`.
*   **Set-Top Box Req:** `MainWindow` defaults to windowed mode. **Violation.** It must default to Fullscreen (or `ShowMaximized` with no frame) per `01_SYSTEM_ARCHITECTURE.md`.

### 3.2. Coding Standards
*   **Type Hinting:** Generally good, but strict Linting issues exist (Forward References).
*   **i18n:** **Violation.** Several user-facing strings in `library_item_delegate.py` are hardcoded without translation wrappers.

---

## 4. Detailed Code Review Findings

### 4.1. `src/controllers/app_controller.py`
*   **[Minor] Unused Import:** `field` is imported from `dataclasses` but not used.
*   **[Minor] Unused Context:** `handle_action(self, action, context)` receives `context`, but the specific state handlers (e.g., `LibraryRootHandler`) do not use it.
    *   *Recommendation:* Keep the signature for future extensibility (Interface Segregation), but linting might complain.
*   **[Critical] Logic Gaps:** The controller relies on `self._main_window` being bound. If `bootstrap()` is called before binding, it may crash.

### 4.2. `src/ui/components/library_item_delegate.py`
*   **[Major] Missing Translations:**
    *   `"No\nImage"`
    *   `"Unknown Title"`
    *   `"Season %s"`
    *   These strings are hardcoded. They must use `src.utils.i18n.tr()` to be localizable.
*   **[Minor] Unused Imports:** `Any`, `PipelineState` are imported but unused.
*   **[Minor] Unused Logic:** `item_type` is assigned in `_draw_metadata` but never used.

### 4.3. `src/ui/components/library_view.py`
*   **[Minor] Unused Constants:** `FONT_SIZE_BODY` and `TEXT_PRIMARY` are imported but not used (styling is handled via Delegate or Stylesheet).
*   **[Logic] `_on_selection_changed`:** The `else` branch emits an empty dict `{}`. This is actually **correct** behavior (clearing the selection in the controller), but the variable `previous` is indeed unused.

### 4.4. `src/ui/components/toast_notification.py`
*   **[Minor] Type Mismatch:** The property `level` returns `self._level`. Linter notes `self._level` is initialized as a specific string, but the return type hint `ToastLevel` (Literal) might conflict if not cast explicitly.
*   **[Clean Code] Unused Args:** `speed` in `_on_download_progress` and `path` in `_on_download_completed` are unused. This is fine for slot signatures, but can be marked with `_` (e.g., `_speed`) to indicate intent.

### 4.5. `src/ui/windows/main_window.py`
*   **[Major] Window State:** Application starts in default windowed mode.
    *   *Fix:* Add `self.showFullScreen()` or `self.setWindowState(Qt.WindowFullScreen)` in `__init__` or `bootstrap`.
*   **[Minor] Missing Type Hint:** `resizeEvent(self, event)` is missing the type hint for `event` (should be `QResizeEvent`).

### 4.6. `src/ui/input_manager.py`
*   **[Clean Code] Dead Code:** `reset_debounce` is defined but never called by the application logic.

### 4.7. `src/utils/i18n.py` & Translation
*   **[Minor] Source Dictionary:** The `create_translation_source` dictionary *does* contain `AppController` keys in the python file provided, but the reviewer noted the `.ts` file (not provided in context) might be missing them.
*   **[Architecture]** The manual dictionary maintenance in `create_translation_source` is error-prone. Standard Qt `lupdate` parses source code for `tr()` calls automatically.
    *   *Recommendation:* Ensure all strings in code are wrapped in `tr()`, then reliance on this manual dictionary can be removed in favor of standard Qt tools.

---

## 5. Action Items for Phase 3 Completion

1.  **Refactor `AppController` Tests:** Do not accept 52% coverage. Mock the `DatabaseManager` and `MainWindow` to test the logic flow of `handle_action` -> `activate_selected` -> `transition_to`. Target >80%.
2.  **Fix i18n:** Wrap all hardcoded strings in `library_item_delegate.py` with the translation helper.
3.  **Fullscreen:** Force fullscreen mode in `MainWindow`.
4.  **Cleanup:** Remove unused imports in `library_item_delegate.py` and `library_view.py`.
5.  **Type Safety:** Add `from __future__ import annotations` to files using string-based forward references for cleaner syntax (optional but recommended for Python 3.11).
