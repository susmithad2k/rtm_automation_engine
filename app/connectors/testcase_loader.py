import csv
from typing import List, Dict


def read_testcases_from_csv(file_path: str) -> List[Dict[str, str]]:
    """
    Read test cases from a CSV file
    
    Args:
        file_path: Path to the CSV file
        
    Returns:
        List of dictionaries containing test case data
    """
    testcases = []
    
    with open(file_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            testcase = parse_testcase_row(row)
            testcases.append(testcase)
    
    return testcases


def parse_testcase_row(row: Dict[str, str]) -> Dict[str, str]:
    """
    Parse a CSV row into a test case object
    
    Args:
        row: Dictionary representing a CSV row
        
    Returns:
        Parsed test case dictionary
    """
    testcase = {
        'name': row.get('name', ''),
        'steps': row.get('steps', ''),
        'id': row.get('id', ''),
        'description': row.get('description', ''),
        'expected_result': row.get('expected_result', '')
    }
    
    return testcase
