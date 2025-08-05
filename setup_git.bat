@echo off
echo 🏦 M0/M1 Card Terminal - Git Setup
echo ================================

echo.
echo 1. Initializing Git repository...
git init

echo.
echo 2. Adding all files...
git add .

echo.
echo 3. Creating initial commit...
git commit -m "Initial M0/M1 Card Terminal with crypto payouts"

echo.
echo 4. Setting main branch...
git branch -M main

echo.
echo ✅ Git repository initialized!
echo.
echo Next steps:
echo 1. Create GitHub repository: https://github.com/new
echo 2. Run: git remote add origin https://github.com/yourusername/m0-m1-terminal.git
echo 3. Run: git push -u origin main
echo 4. Deploy on Render: https://render.com
echo.
pause
