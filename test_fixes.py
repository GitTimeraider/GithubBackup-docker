#!/usr/bin/env python3
"""
Test script to verify the fixes for template and scheduler issues
"""

import os
import sys
from flask import Flask
from jinja2 import Environment, FileSystemLoader, TemplateError

def test_template_syntax():
    """Test if the edit_repository.html template has valid syntax"""
    print("Testing template syntax...")
    
    try:
        # Create a Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        
        # Try to load and parse the template
        template = env.get_template('edit_repository.html')
        print("✅ edit_repository.html syntax is valid")
        return True
        
    except TemplateError as e:
        print(f"❌ Template syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading template: {e}")
        return False

def test_app_imports():
    """Test if the app can be imported without errors"""
    print("Testing app imports...")
    
    try:
        # Set environment variables to avoid missing config errors
        os.environ.setdefault('SECRET_KEY', 'test-key')
        os.environ.setdefault('DATABASE_URL', 'sqlite:///test.db')
        
        # Try to import the app
        sys.path.insert(0, os.path.dirname(__file__))
        import app
        print("✅ App imports successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error importing app: {e}")
        return False

def main():
    print("Running fix verification tests...\n")
    
    template_ok = test_template_syntax()
    app_ok = test_app_imports()
    
    print(f"\n{'='*50}")
    print("Test Results:")
    print(f"Template syntax: {'✅ PASS' if template_ok else '❌ FAIL'}")
    print(f"App imports: {'✅ PASS' if app_ok else '❌ FAIL'}")
    
    if template_ok and app_ok:
        print("\n🎉 All tests passed! The fixes should work correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
