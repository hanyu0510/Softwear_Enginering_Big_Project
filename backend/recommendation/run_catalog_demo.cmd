@echo off
cd /d "%~dp0.."
set "RECOMMENDATION_MODE=catalog_live_weather"
set "RECOMMENDATION_PORT=8011"
echo Backend UI: http://127.0.0.1:8011/
python -m recommendation.api
pause
