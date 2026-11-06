@echo off
rem Start everything Guardian needs on this machine: Qwen, guardian-ai, the Django web app and the
rem HTTPS proxy (Caddy). Double-click it at this desktop: programs started here keep running after
rem you close the window, unlike programs started over SSH. See plan.md section 20.
wsl -d Ubuntu-24.04 -- bash /home/hackathon/guardian-ai/scripts/start_all.sh
echo.
echo Guardian should now be live at https://137-63-190-11.sslip.io
pause
