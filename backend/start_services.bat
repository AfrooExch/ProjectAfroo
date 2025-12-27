@echo off
echo ================================================================================
echo Starting MongoDB and Redis with Docker
echo ================================================================================
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo.
    echo Please install Docker Desktop from:
    echo https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

echo [OK] Docker is available

REM Check and start MongoDB
echo.
echo [INFO] Checking MongoDB...
docker ps | findstr "afroo-mongodb" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting MongoDB container...
    docker run -d --name afroo-mongodb -p 27017:27017 mongo:latest
    if errorlevel 1 (
        echo [WARNING] Container might already exist but stopped
        docker start afroo-mongodb
    )
    echo [OK] MongoDB started on port 27017
) else (
    echo [OK] MongoDB is already running
)

REM Check and start Redis
echo.
echo [INFO] Checking Redis...
docker ps | findstr "afroo-redis" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Starting Redis container...
    docker run -d --name afroo-redis -p 6379:6379 redis:latest
    if errorlevel 1 (
        echo [WARNING] Container might already exist but stopped
        docker start afroo-redis
    )
    echo [OK] Redis started on port 6379
) else (
    echo [OK] Redis is already running
)

echo.
echo ================================================================================
echo Services Started Successfully!
echo ================================================================================
echo.
echo MongoDB: localhost:27017
echo Redis: localhost:6379
echo.
echo To stop services:
echo   docker stop afroo-mongodb afroo-redis
echo.
echo To view logs:
echo   docker logs afroo-mongodb
echo   docker logs afroo-redis
echo.
echo Ready to run: run_tests.bat
echo.
pause
