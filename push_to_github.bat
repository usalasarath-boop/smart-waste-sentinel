@echo off
setlocal
title Push Smart Waste Sentinel to GitHub

echo ==============================================================
echo       Smart Waste Sentinel - Push to GitHub Utility
echo ==============================================================
echo.
echo GitHub Account : usalasarath-boop
echo Target Remote  : https://github.com/usalasarath-boop/smart-waste-sentinel.git
echo.
echo IMPORTANT NOTE:
echo Before pushing, make sure you have created an empty repository on GitHub:
echo 1. Open: https://github.com/new
echo 2. Repository name: smart-waste-sentinel
echo 3. Keep "Add a README", ".gitignore", and "license" UNCHECKED
echo 4. Click "Create repository"
echo.
echo ==============================================================
set /p REPO_NAME="Press ENTER to use 'smart-waste-sentinel' or type a custom repo name: "

if "%REPO_NAME%"=="" (
    set TARGET_REPO=smart-waste-sentinel
) else (
    set TARGET_REPO=%REPO_NAME%
)

set GIT_EXE="%~dp0git\cmd\git.exe"
if not exist %GIT_EXE% (
    set GIT_EXE=git
)

echo.
echo Configuring remote origin to: https://github.com/usalasarath-boop/%TARGET_REPO%.git
%GIT_EXE% remote set-url origin https://github.com/usalasarath-boop/%TARGET_REPO%.git

echo.
echo Pushing branch 'main' to GitHub...
echo (If prompted, log in with your browser or Personal Access Token)
echo.
%GIT_EXE% push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ==============================================================
    echo [SUCCESS] Project successfully published to:
    echo https://github.com/usalasarath-boop/%TARGET_REPO%
    echo ==============================================================
) else (
    echo.
    echo [NOTICE] If the push failed, verify that:
    echo 1. You created the repository at: https://github.com/new
    echo 2. The repository name matches '%TARGET_REPO%'
)

echo.
pause
