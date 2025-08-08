import json
import pandas as pd

# Path to your JSON input and output Excel file
JSON_INPUT = r'json\extracted_insurance_fields.json'
EXCEL_OUTPUT = 'output.xlsx'


def flatten_insurance_data(data):
    records = []
    # Handle list of blocks
    if isinstance(data, list):
        for block in data:
            key = block.get('insurance_type', 'Unknown')
            records.extend(flatten_insurance_data({key: block}))
        return records

    # Handle dict of blocks
    if isinstance(data, dict):
        for insurance_key, block in data.items():
            insurance_type = block.get('insurance_type', insurance_key)
            extracted = block.get('extracted_fields', {})
            if not isinstance(extracted, dict):
                continue
            for section, fields in extracted.items():
                # Only proceed if fields is dict or list
                if isinstance(fields, dict):
                    records.extend(_flatten_fields(insurance_type, section, fields))
                elif isinstance(fields, list):
                    for fld in fields:
                        if isinstance(fld, dict):
                            records.extend(_flatten_fields(insurance_type, section, fld))
                else:
                    # Skip unsupported types
                    continue
    return records


def _flatten_fields(insurance_type, section, fields_dict):
    rows = []
    if not isinstance(fields_dict, dict):
        return rows
    for field_name, info in fields_dict.items():
        if isinstance(info, dict):
            rows.append(_make_record(insurance_type, section, field_name, info))
        elif isinstance(info, list):
            for entry in info:
                if isinstance(entry, dict):
                    rows.append(_make_record(insurance_type, section, field_name, entry))
        # Ignore other types
    return rows


def _make_record(insurance_type, section, field_name, info):
    # Extract and format value
    raw_values = info.get('value')
    if isinstance(raw_values, list):
        value = ', '.join(str(v) for v in raw_values)
    else:
        value = str(raw_values) if raw_values is not None else ''

    # Extract confidence
    confidence = info.get('confidence')

    # Extract and format pages
    pages = info.get('source_page_numbers')
    pages_str = ', '.join(str(p) for p in pages) if isinstance(pages, list) else ''

    return {
        'insurance_type': insurance_type,
        'section': section,
        'field': field_name,
        'value': value,
        'confidence': confidence,
        'source_pages': pages_str
    }


def main():
    # Load JSON data
    with open(JSON_INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Flatten into tabular records
    rows = flatten_insurance_data(data)

    # Create DataFrame and save to Excel
    df = pd.DataFrame(rows)
    df.to_excel(EXCEL_OUTPUT, index=False)
    print(f"Data successfully written to {EXCEL_OUTPUT}")


if __name__ == '__main__':
    main()
