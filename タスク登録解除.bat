@echo off
chcp 65001 > nul
cd /d "%~dp0"
python -c "import subprocess; subprocess.run(['schtasks', '/Delete', '/TN', 'JobSearchAutoRun', '/F'], shell=True)"
echo.
echo 【完了】タスクスケジューラの登録を解除（削除）しました。
pause