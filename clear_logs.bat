@echo off
cd /d "%~dp0"
del /f /q logs_api.log
del /f /q logs_debug_image_response.txt
del /f /q logs_raw_requests.log
