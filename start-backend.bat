@echo off
echo Starting IT BOM Backend Server...
echo.
echo Backend will run at: http://localhost:8000
echo API docs will be at: http://localhost:8000/docs
echo.
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
