@echo off
chcp 65001 > nul
echo ===================================================
echo  求人検索およびAI判定スクリプトを開始します
echo ===================================================

cd /d "C:\Users\Owner\Documents\アスパーク\研修7_Search_Jobs\GoogleJobs-AI-Scraper-Filter"
python job_search.py

echo ===================================================
echo  処理が終了しました
echo ===================================================
pause