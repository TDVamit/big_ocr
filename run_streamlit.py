#!/usr/bin/env python3
"""
Script to run the Streamlit Insurance Document Processor Frontend
"""
import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "streamlit_requirements.txt"])
        print("✅ Requirements installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        sys.exit(1)

def run_streamlit():
    """Run the Streamlit app"""
    try:
        print("🚀 Starting Streamlit Insurance Document Processor...")
        print("📄 Access the app at: http://localhost:8501")
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "streamlit-frontend.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ])
    except KeyboardInterrupt:
        print("\n⏹️  Streamlit app stopped.")
    except Exception as e:
        print(f"❌ Error running Streamlit: {e}")

def main():
    """Main function"""
    print("🏢 Insurance Document Processor - Frontend Launcher")
    print("=" * 50)
    
    # Check if requirements file exists
    if os.path.exists("streamlit_requirements.txt"):
        print("📦 Installing requirements...")
        install_requirements()
    
    # Run Streamlit
    run_streamlit()

if __name__ == "__main__":
    main() 