
def add_padding_pages(categorized_pages, total_pages):
    """Add padding pages (previous and next) to each insurance type group"""
    print(f"  📄 Adding padding pages to categorized results...")
    
    padded_results = {}
    
    for insurance_type, pages_info in categorized_pages.items():
        if insurance_type == "Common":
            # Don't add padding to Common type
            padded_results[insurance_type] = pages_info
            continue
            
        # Extract page numbers
        page_numbers = []
        for page_key, page_info in pages_info.items():
            if isinstance(page_info, dict) and 'page_num' in page_info:
                page_numbers.append(page_info['page_num'])
            elif page_key.startswith('page_'):
                # Extract page number from key
                try:
                    page_num = int(page_key.split('_')[1])
                    page_numbers.append(page_num)
                except:
                    continue
        
        if not page_numbers:
            padded_results[insurance_type] = pages_info
            continue
            
        # Add padding (previous and next page for each page)
        padded_page_numbers = set(page_numbers)
        
        for page_num in page_numbers:
            # Add previous page
            if page_num > 1:
                padded_page_numbers.add(page_num - 1)
            # Add next page
            if page_num < total_pages:
                padded_page_numbers.add(page_num + 1)
        
        # Create padded results
        padded_info = {}
        for page_num in sorted(padded_page_numbers):
            page_key = f"page_{page_num}"
            if page_key in pages_info:
                # Original page with analysis
                padded_info[page_key] = pages_info[page_key]
            else:
                # Padding page
                padded_info[page_key] = {
                    "page_num": page_num,
                    "is_padding": True,
                    "reason": "Added as context padding"
                }
        
        padded_results[insurance_type] = padded_info
        
        original_count = len(page_numbers)
        padded_count = len(padded_page_numbers)
        print(f"    • {insurance_type}: {original_count} → {padded_count} pages (added {padded_count - original_count} padding)")
    
    return padded_results

def redistribute_common_pages(padded_results):
    """Redistribute Common pages to closest insurance types and remove Common category"""
    print(f"  🔄 Redistributing Common pages to closest insurance types...")
    
    if "Common" not in padded_results:
        print(f"    ✅ No Common pages found - no redistribution needed")
        return padded_results
    
    common_pages = padded_results["Common"]
    other_insurance_types = {k: v for k, v in padded_results.items() if k != "Common"}
    
    if not other_insurance_types:
        print(f"    ⚠️  No other insurance types found - keeping Common pages as-is")
        return padded_results
    
    print(f"    📄 Found {len(common_pages)} Common pages to redistribute")
    
    # Step 1: Remove Common pages that already exist in other insurance types
    remaining_common_pages = {}
    removed_duplicates = 0
    
    for page_key, page_info in common_pages.items():
        is_duplicate = False
        for insurance_type, type_pages in other_insurance_types.items():
            if page_key in type_pages:
                is_duplicate = True
                removed_duplicates += 1
                print(f"      • Removing {page_key} from Common (already in {insurance_type})")
                break
        
        if not is_duplicate:
            remaining_common_pages[page_key] = page_info
    
    print(f"    🗑️  Removed {removed_duplicates} duplicate pages from Common")
    print(f"    📄 {len(remaining_common_pages)} Common pages remaining for redistribution")
    
    if not remaining_common_pages:
        print(f"    ✅ No remaining Common pages - redistribution complete")
        # Return results without Common
        return other_insurance_types
    
    # Step 2: Distribute remaining Common pages to closest insurance types
    redistributed_results = dict(other_insurance_types)  # Copy other types
    
    for page_key, page_info in remaining_common_pages.items():
        # Extract page number from Common page
        if isinstance(page_info, dict) and 'page_num' in page_info:
            common_page_num = page_info['page_num']
        elif page_key.startswith('page_'):
            try:
                common_page_num = int(page_key.split('_')[1])
            except:
                print(f"      ⚠️  Could not extract page number from {page_key}, skipping...")
                continue
        
        # Find closest insurance type
        closest_insurance_type = None
        min_distance = float('inf')
        
        for insurance_type, type_pages in redistributed_results.items():
            # Get all page numbers for this insurance type
            type_page_numbers = []
            for type_page_key, type_page_info in type_pages.items():
                if isinstance(type_page_info, dict) and 'page_num' in type_page_info:
                    type_page_numbers.append(type_page_info['page_num'])
                elif type_page_key.startswith('page_'):
                    try:
                        type_page_num = int(type_page_key.split('_')[1])
                        type_page_numbers.append(type_page_num)
                    except:
                        continue
            
            if not type_page_numbers:
                continue
            
            # Calculate minimum distance to any page in this insurance type
            distances = [abs(common_page_num - type_page_num) for type_page_num in type_page_numbers]
            min_type_distance = min(distances)
            
            if min_type_distance < min_distance:
                min_distance = min_type_distance
                closest_insurance_type = insurance_type
        
        # Add Common page to closest insurance type
        if closest_insurance_type:
            # Mark the page as redistributed from Common
            redistributed_page_info = dict(page_info)
            redistributed_page_info['redistributed_from'] = 'Common'
            redistributed_page_info['distance_to_closest'] = min_distance
            
            redistributed_results[closest_insurance_type][page_key] = redistributed_page_info
            print(f"      • {page_key} (page {common_page_num}) → {closest_insurance_type} (distance: {min_distance})")
        else:
            print(f"      ⚠️  Could not find closest insurance type for {page_key}")
    
    # Print redistribution summary
    print(f"    📊 Redistribution Summary:")
    for insurance_type, type_pages in redistributed_results.items():
        redistributed_count = len([p for p in type_pages.values() if isinstance(p, dict) and p.get('redistributed_from') == 'Common'])
        if redistributed_count > 0:
            print(f"      • {insurance_type}: +{redistributed_count} pages from Common")
    
    print(f"    ✅ Common redistribution complete - Common category removed")
    return redistributed_results