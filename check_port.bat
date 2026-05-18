@echo off
python -c "import socket; s=socket.create_connection(('127.0.0.1',8000),timeout=3); print('PORT 8000 OPEN - OK'); s.close()" 2>&1 && goto ok
echo PORT 8000 FAILED - backend not reachable
goto end
:ok
python -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3); print('HTTP OK:', r.read().decode())" 2>&1
:end
pause
