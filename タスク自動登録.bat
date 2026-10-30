@echo off
chcp 65001 > nul
cd /d "%~dp0"

:: バッチファイルの絶対パスを変数に格納
set "BAT_FILE=%~dp0run_job_search.bat"

:: Pythonスクリプトを外部ファイルとして実行するか、raw文字列を使う形に修正
::python -c "import subprocess, os; bat = os.path.abspath(r'%BAT_FILE%'); subprocess.run(['schtasks', '/Create', '/TN', 'JobSearchAutoRun', '/TR', f'\"{bat}\"', '/SC', 'DAILY', '/ST', '08:00', '/F'], shell=True)"
python register_task.py register

echo.
echo 【完了】タスクスケジューラへの登録処理が終了しました。
pause