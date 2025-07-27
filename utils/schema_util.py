import json
import re

schema_json = json.load(open(r"json\schema.json"))

def get_insurance_types_from_schema():
    """Extract insurance type keys from schema.json (excluding 'description' and 'schema')"""
    try:
        insurance_types = []
        insurance_types.extend(schema_json.keys())        
        return insurance_types
        
    except Exception as e:
        print(f"⚠️  Error reading schema file: {e}")
        return ["Commercial Auto", "Homeowners", "Commercial Property", "Workers Compensation", "General Liability","Umbrella Excess","Cyber Liability","Professional Liability","Directors & Officers"]

def get_all_schema_keys():
    """Extract all field keys recursively from schema.json for AI context"""
    schema_keys = get_insurance_types_from_schema()
    schema_keys.extend(['description', 'schema'])
    def extract_keys(data, keys_list):
        if isinstance(data, dict):
            for key, value in data.items():
                if key not in schema_keys:
                    keys_list.append(key)
                extract_keys(value, keys_list)
        elif isinstance(data, list):
            for item in data:
                extract_keys(item, keys_list)
    try:
        all_keys = []
        extract_keys(schema_json, all_keys)
        # Remove duplicates and sort
        unique_keys = list(set(all_keys))
        unique_keys.sort()
        return unique_keys
        
    except Exception as e:
        print(f"⚠️  Error reading schema file: {e}")
        return []
    
def get_specific_fields_of_insurance_type(insurance_type):
    try:
        if insurance_type not in schema_json:
            if insurance_type == "Common":
                return {}
            print(f"⚠️  Insurance type '{insurance_type}' not found in schema returning all fields.")
            all_fields = {"schema":{}}
            for key,value in schema_json.items():
                all_fields["schema"].update(value["schema"])
            return all_fields
        # Search for insurance type in data keys using regex pattern
        pattern = re.compile(insurance_type, re.IGNORECASE)
        matching_keys = [k for k in schema_json.keys() if pattern.search(k)]
        return schema_json[matching_keys[0]] if matching_keys else {}
    except Exception as e:
        print(f"⚠️  Error reading schema file: {e}")
        return {}