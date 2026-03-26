#!/usr/bin/env python3
"""
Test script for the Streamlit app pipeline functionality.
This tests the core functions without running the Streamlit UI.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Import the app functions
from app import run_extraction, run_generation, detect_file_type, build_user_message

def test_pipeline():
    """Test the complete pipeline with sample data."""
    print("🧪 Testing Streamlit App Pipeline...")
    
    # Load sample data files
    data_dir = Path("data")
    if not data_dir.exists():
        print("❌ Data directory not found")
        return
    
    # Read all files in data directory
    file_contents = {}
    for file_path in data_dir.glob("*"):
        if file_path.is_file() and file_path.suffix in ['.json', '.txt']:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_contents[file_path.name] = f.read()
    
    print(f"📁 Loaded {len(file_contents)} files:")
    for name in file_contents.keys():
        print(f"   - {name}")
    
    # Test file type detection
    print("\n🔍 Testing file type detection:")
    files_by_type = {}
    for filename, content in file_contents.items():
        file_type = detect_file_type(filename, content)
        files_by_type[file_type] = content
        print(f"   {filename} → {file_type}")
    
    # Test user message building
    print("\n📝 Testing user message building:")
    user_message = build_user_message(files_by_type)
    print(f"   Message length: {len(user_message)} characters")
    print(f"   Message preview: {user_message[:200]}...")
    
    # Test extraction (if API key is available)
    if os.getenv("ANTHROPIC_API_KEY"):
        print("\n🤖 Testing incident extraction...")
        try:
            extraction = run_extraction(file_contents)
            print("   ✅ Extraction successful!")
            print(f"   Incident summary: {extraction.get('incident_summary', 'N/A')}")
            print(f"   Affected service: {extraction.get('affected_service', 'N/A')}")
            print(f"   Severity: {extraction.get('severity', 'N/A')}")
            
            # Test communication generation
            print("\n📢 Testing communication generation...")
            comms = run_generation(extraction)
            print("   ✅ Communication generation successful!")
            print(f"   Title: {comms.get('title', 'N/A')}")
            print(f"   Communications: {len(comms.get('communications', []))} stages")
            
            print("\n🎉 Complete pipeline test PASSED!")
            
        except Exception as e:
            print(f"   ❌ Pipeline test failed: {str(e)}")
    else:
        print("\n⚠️  Skipping API tests (no ANTHROPIC_API_KEY found)")
        print("   Set ANTHROPIC_API_KEY in .env file to test complete pipeline")

if __name__ == "__main__":
    load_dotenv()
    test_pipeline()
