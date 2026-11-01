# Previous run-less error shown against a fresh plan

2026-11-01. Owner screenshot: a fresh reviewable plan still displayed
`INSTALLATION_RUN_NOT_FOUND` and the red "Запуск не начался" header. React kept
the previous run-operation error when replacing the plan. After a new plan is
returned without an operation error, App now clears a previous run-less
operation. Actual run objects, history and observation errors remain intact;
failed plan creation does not clear the earlier error. No backend/Core change.
This follows the shared authoritative plan/run status rules in ui-design-01.

Two new App handler tests PASS (fresh plan clears old error; failed creation
retains it). Expanded App/Installation/presentation selection: 161 PASS, 2 FAIL
in existing B4 text assertions ("При отсутствии актуального Verify Core включит
проверку инфраструктуры" and "Состав запуска изменён"). B4 directly imports
InstallationPage, not App; its component, presentation module and tests are
unchanged from HEAD. These failures are outside this fix.

Frontend production and Windows Wails production builds PASS. Actual WebView
reproduction of the stale run lookup and subsequent fresh plan was not
performed; mocked handler tests do not satisfy that acceptance gate. No
installation or plan approval was started for QA. Update the Installer binary;
this frontend-only fix does not require a new runtime bundle.
