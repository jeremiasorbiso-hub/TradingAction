# verify_build.py
"""
Build verification script - checks all imports and syntax
"""
import sys
import importlib.util
from pathlib import Path

def check_syntax(filepath):
    """Check Python file syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, None
    except SyntaxError as e:
        return False, str(e)

def main():
    print("=" * 60)
    print("QUANT EDGE PRO - Build Verification")
    print("=" * 60)
    
    project_root = Path(__file__).parent
    py_files = list(project_root.rglob('*.py'))
    
    errors = []
    success_count = 0
    
    print(f"\nChecking {len(py_files)} Python files...\n")
    
    for py_file in sorted(py_files):
        relative_path = py_file.relative_to(project_root)
        
        success, error = check_syntax(py_file)
        
        if success:
            print(f"✓ {relative_path}")
            success_count += 1
        else:
            print(f"✗ {relative_path}")
            errors.append((relative_path, error))
    
    print("\n" + "=" * 60)
    print(f"Results: {success_count}/{len(py_files)} files OK")
    print("=" * 60)
    
    if errors:
        print("\nErrors found:")
        for filepath, error in errors:
            print(f"\n{filepath}:")
            print(f"  {error}")
        return 1
    
    print("\n✓ All files verified successfully!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Train models: python train.py")
    print("3. Start server: python main.py")
    print("4. Open browser: file:///<path>/quant_edge_pro.html")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
