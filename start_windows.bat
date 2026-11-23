@echo off
setlocal
cd /d "%~dp0"
REM windows-curses finns for Python 3.9-3.13. Prova dem i ordning, annars "python".
for %%V in (3.13 3.12 3.11 3.10 3.9) do (
  py -%%V -c "import sys" >nul 2>&1 && (
    py -%%V -c "import curses" >nul 2>&1 || py -%%V -m pip install windows-curses
    py -%%V eldledning.py
    goto :done
  )
)
python -c "import curses" >nul 2>&1 || python -m pip install windows-curses
python eldledning.py
:done
echo.
echo Om det inte startade: installera Python 3.13 (winget install Python.Python.3.13)
pause
