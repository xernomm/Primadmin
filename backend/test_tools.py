from MCP.tools.cv_tools import extract_cv_from_file, manage_cv_file
import json

print("Testing manage_cv_file:")
try:
    res1 = manage_cv_file(10, 'replace', r"D:\PINET\AI\Primasistant-HR\backend\uploads\cv")
    print(json.dumps(res1, indent=2))
except Exception as e:
    print(f"manage_cv_file Error: {e}")

print("\nTesting extract_cv_from_file:")
try:
    res2 = extract_cv_from_file(10, r"D:\PINET\AI\Primasistant-HR\backend\uploads\cv\CV_Rafael_Richie_EMP010.pdf")
    print(json.dumps(res2, indent=2))
except Exception as e:
    print(f"extract_cv_from_file Error: {e}")
