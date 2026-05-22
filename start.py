"""
GlowCheck 빠른 시작 스크립트
────────────────────────────
python start.py

자동으로:
  1. 필요한 패키지 설치
  2. DB & 샘플 데이터 초기화
  3. Flask 서버 실행 → http://localhost:5000
"""

import subprocess
import sys
import os

REQUIRED = ['flask', 'flask-cors', 'requests', 'beautifulsoup4', 'lxml']

def install_packages():
    print("📦 패키지 확인 중…")
    for pkg in REQUIRED:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            print(f"  Installing {pkg}…")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg, '-q'])
    print("✅ 패키지 준비 완료\n")

def seed_if_empty():
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'glowcheck.db')
    if not os.path.exists(db_path):
        print("🌱 샘플 데이터 초기화 중…")
        subprocess.check_call([sys.executable, 'seed_data.py'])
        print()

def run_server():
    print("🚀 GlowCheck 서버 시작!")
    print("   브라우저에서 열기 → http://localhost:5000\n")
    print("   종료: Ctrl + C\n")
    os.execv(sys.executable, [sys.executable, 'app.py'])

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    install_packages()
    seed_if_empty()
    run_server()
