import streamlit as st
import asyncio
import json
import os
import time
from pathlib import Path
import tempfile
import nest_asyncio
import fitz  # PyMuPDF for PDF to image conversion
from main import main_async as main_ocr_async

# Enable nested async loops for Streamlit
nest_asyncio.apply()

# Import the main functions

# Configure Streamlit page
st.set_page_config(
    page_title="Insurance Document Processor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .step-container {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 5px solid #1f77b4;
    }
    .field-container {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #e1e5e9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .field-header {
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .field-value {
        color: #333333;
        font-weight: normal;
    }
    .source-button {
        margin: 2px;
        padding: 2px 8px;
        font-size: 0.8rem;
        background-color: #007bff;
        color: white;
        border-radius: 4px;
        cursor: pointer;
    }
    .confidence-high { color: #28a745; font-weight: bold; }
    .confidence-medium { color: #ffc107; font-weight: bold; }
    .confidence-low { color: #dc3545; font-weight: bold; }
    .scrollable-area {
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid #e1e5e9;
        border-radius: 8px;
        padding: 1rem;
        background-color: #ffffff;
    }
    .json-container {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid #dee2e6;
    }
    .pdf-image-container {
        border: 2px solid #e1e5e9;
        border-radius: 8px;
        background-color: #ffffff;
        padding: 10px;
        text-align: center;
    }
    .stButton > button {
        background-color: #007bff;
        color: white;
        border: 1px solid #007bff;
        border-radius: 4px;
        padding: 0.25rem 0.75rem;
        font-size: 0.875rem;
        line-height: 1.5;
    }
    .stButton > button:hover {
        background-color: #0056b3;
        border-color: #0056b3;
    }
    .stButton > button:disabled {
        background-color: #6c757d;
        border-color: #6c757d;
        cursor: not-allowed;
    }
</style>
""", unsafe_allow_html=True)

def ensure_pdfimages_directory():
    """Ensure the pdfimages directory exists"""
    pdf_images_dir = Path("pdfimages")
    pdf_images_dir.mkdir(exist_ok=True)
    return str(pdf_images_dir)

def convert_pdf_to_images(pdf_file):
    """Convert all PDF pages to images and store them in pdfimages directory"""
    pdf_images_dir = ensure_pdfimages_directory()
    
    # Create a unique folder for this PDF based on filename and size
    pdf_hash = f"{pdf_file.name}_{len(pdf_file.getvalue())}"
    pdf_specific_dir = Path(pdf_images_dir) / pdf_hash
    
    # Check if images already exist
    if pdf_specific_dir.exists() and len(list(pdf_specific_dir.glob("*.png"))) > 0:
        # Load existing images
        image_files = sorted(pdf_specific_dir.glob("*.png"), key=lambda x: int(x.stem.split('_')[-1]))
        
        images = []
        for img_file in image_files:
            with open(img_file, 'rb') as f:
                images.append(f.read())
        
        # Store in session state
        st.session_state.pdf_images = images
        st.session_state.total_pages = len(images)
        st.session_state.current_pdf_name = pdf_file.name
        st.session_state.pdf_images_path = str(pdf_specific_dir)
        
        return True, len(images)
    
    # Convert PDF to images if not already done
    if 'pdf_images' not in st.session_state or st.session_state.get('current_pdf_name') != pdf_file.name:
        
        with st.spinner("🔄 Converting PDF to images..."):
            doc = None
            temp_pdf_path = None
            
            try:
                # Create directory for this PDF
                pdf_specific_dir.mkdir(exist_ok=True)
                
                # Save PDF to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(pdf_file.getvalue())
                    temp_pdf_path = tmp_file.name
                
                # Open PDF with PyMuPDF
                doc = fitz.open(temp_pdf_path)
                total_pages = len(doc)
                
                # Convert all pages to images
                images = []
                for page_num in range(total_pages):
                    page = doc.load_page(page_num)
                    # Use higher resolution for better quality
                    mat = fitz.Matrix(2.0, 2.0)  # 2x scale factor
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    images.append(img_data)
                    
                    # Save image to disk
                    img_path = pdf_specific_dir / f"page_{page_num + 1:04d}.png"
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                
                # Store in session state
                st.session_state.pdf_images = images
                st.session_state.total_pages = total_pages
                st.session_state.current_pdf_name = pdf_file.name
                st.session_state.pdf_images_path = str(pdf_specific_dir)
                
                return True, total_pages
                
            except Exception as e:
                st.error(f"Error converting PDF to images: {str(e)}")
                return False, 0
            finally:
                # Clean up resources
                try:
                    if doc:
                        doc.close()
                except:
                    pass
                try:
                    if temp_pdf_path and os.path.exists(temp_pdf_path):
                        os.unlink(temp_pdf_path)
                except:
                    pass
    
    return True, st.session_state.get('total_pages', 0)

def display_pdf_as_images(pdf_file, current_page):
    """Display PDF page as image with simple navigation"""
    
    # Convert PDF to images if not already done
    success, total_pages = convert_pdf_to_images(pdf_file)
    
    if not success or total_pages == 0:
        st.error("Failed to convert PDF to images")
        return 1
    
    # Update session state if needed
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = 1
    
    # Ensure current page is within bounds
    current_page = max(1, min(current_page, total_pages))
    col1, col2 = st.columns(2)

    with col1:
        st.header("📄 PDF Document")

    with col2:
    # Simple page input only
        new_page = st.number_input(
            "Go to page:", 
            min_value=1, 
            max_value=total_pages,
            value=current_page,
            key="page_input"
        )
    if new_page != current_page:
        st.session_state.selected_page = new_page
        st.rerun()
    
    # Display the current page image
    if 'pdf_images' in st.session_state and len(st.session_state.pdf_images) >= current_page:
        st.image(
            st.session_state.pdf_images[current_page - 1], 
            caption=f"Page {current_page} of {total_pages}",
            use_container_width=True  # Fixed deprecation warning
        )
    
    return total_pages

def get_confidence_color(confidence):
    """Get color class based on confidence score"""
    if confidence >= 0.8:
        return "confidence-high"
    elif confidence >= 0.5:
        return "confidence-medium"
    else:
        return "confidence-low"

# Global counter for unique button keys
_button_counter = 0

def display_field_value(field_name, field_data, pdf_file, context_path=""):
    """Display a field with its value, confidence, and source buttons"""
    global _button_counter
    
    value = field_data.get('value', field_data.get('source', 'N/A'))
    confidence = field_data.get('confidence', 0.0)
    # Look for source_page_numbers first, then fall back to source
    source_pages = field_data.get('source_page_numbers', field_data.get('source', []))
    
    # Handle different value types
    if isinstance(value, list):
        if len(value) > 0:
            display_value = ", ".join(str(v) for v in value)
        else:
            display_value = "No data"
    elif value is None:
        display_value = "No data"
    else:
        display_value = str(value)
    
    confidence_class = get_confidence_color(confidence)
    
    # Create the field container with better contrast
    field_html = f"""
    <div class="field-container">
        <div class="field-header">{field_name.replace('_', ' ').title()}</div>
        <div class="field-value"><strong>Value:</strong> {display_value}</div>
    """
    
    if confidence > 0:
        field_html += f'<div class="field-value"><strong>Confidence:</strong> <span class="{confidence_class}">{confidence:.2f}</span></div>'
    
    if source_pages:
        field_html += '<div class="field-value"><strong>Source Pages:</strong> '
        for page in source_pages:
            field_html += f'<span class="source-button">Page {page}</span> '
        field_html += '</div>'
    
    field_html += '</div>'
    
    st.markdown(field_html, unsafe_allow_html=True)
    
    # Source page buttons that actually work - show ALL pages, not limited to 8
    if source_pages:
        st.write("**Quick Navigation:**")
        pages_per_row = 10
        total_pages = len(source_pages)
        
        for row_start in range(0, total_pages, pages_per_row):
            row_end = min(row_start + pages_per_row, total_pages)
            row_pages = source_pages[row_start:row_end]
            
            cols = st.columns(len(row_pages))
            for i, page in enumerate(row_pages):
                with cols[i]:
                    # Use a unique key that includes the page number and more unique identifiers
                    
                    # Create a more unique key by including the context path, field name, page, row position, column index, and global counter
                    context_safe = context_path.replace(" ", "_").replace("    ", "_").replace("  ", "_")
                    _button_counter += 1
                    unique_id = f"{context_safe}_{field_name}_{page}_{row_start}_{i}_{_button_counter}"
                    button_key = f"nav_to_page_{page}_{unique_id}"
                    if st.button(f"📄 {page}", key=button_key, help=f"Navigate to page {page}"):
                        st.session_state.selected_page = int(page)
                        st.success(f"✅ Navigated to page {page}")
                        st.rerun()

def display_insurance_section(section_name, section_data, pdf_file):
    """Display an insurance section with all its fields"""
    st.subheader(f"📋 {section_name.replace('_', ' ').title()}")
    
    with st.expander(f"View {section_name} Details", expanded=True):
        # Handle nested structure
        for field_name, field_data in section_data.items():
            if isinstance(field_data, dict):
                if 'value' in field_data or 'source' in field_data:
                    # This is a field with value/confidence/source
                    display_field_value(field_name, field_data, pdf_file, f"{section_name}_{field_name}")
                else:
                    # This is a nested section
                    st.markdown(f"**{field_name.replace('_', ' ').title()}:**")
                    for sub_field, sub_data in field_data.items():
                        if isinstance(sub_data, dict):
                            display_field_value(f"  {sub_field}", sub_data, pdf_file, f"{section_name}_{field_name}_{sub_field}")
                        else:
                            st.markdown(f"  **{sub_field}:** {sub_data}")
            elif isinstance(field_data, list):
                # Handle list of items (like vehicles)
                st.markdown(f"**{field_name.replace('_', ' ').title()}:**")
                for i, item in enumerate(field_data):
                    st.markdown(f"  **Item {i+1}:**")
                    if isinstance(item, dict):
                        for sub_field, sub_data in item.items():
                            if isinstance(sub_data, dict) and ('value' in sub_data or 'source' in sub_data):
                                display_field_value(f"    {sub_field}", sub_data, pdf_file, f"{section_name}_{field_name}_item_{i}_{sub_field}")
                            else:
                                st.markdown(f"    **{sub_field}:** {sub_data}")
            else:
                st.markdown(f"**{field_name}:** {field_data}")

def run_processing_script_sync(script_choice, pdf_path, use_cache, pdf_images_path=None, add_padding=True):
    """Run the selected processing script synchronously"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        if script_choice == "OCR-based (main.py)":
            result = loop.run_until_complete(main_ocr_async(pdf_path, use_cache, pdf_images_path, add_padding))
        # elif script_choice == "Vision-based (main-vision.py)":
        #     result = loop.run_until_complete(main_vision_async(pdf_path, use_cache, pdf_images_path, add_padding))
        # elif script_choice == "Image-based (main-image.py)":
        #     result = loop.run_until_complete(main_image_async(pdf_path, use_cache, pdf_images_path, add_padding))
        
        loop.close()
        return True, result
    except Exception as e:
        return False, str(e)

def load_json_results(script_choice):
    """Load the appropriate JSON results file"""
    if script_choice == "OCR-based (main.py)":
        json_path = "json/extracted_insurance_fields.json"
    elif script_choice == "Vision-based (main-vision.py)":
        json_path = "json/extracted_insurance_fields.json"
    elif script_choice == "Image-based (main-image.py)":
        json_path = "json/extracted_insurance_fields_image.json"
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading JSON results: {str(e)}")
            return None
    return None

def load_all_json_files():
    """Load all available JSON files for comprehensive display"""
    json_files = {}
    
    # Define all possible JSON files
    possible_files = {
        "OCR Results": "json/ocr_results.json",
        "Vision Results": "json/vision_results.json", 
        "Extracted Insurance Fields": "json/extracted_insurance_fields.json",
        "Extracted Insurance Fields (Image)": "json/extracted_insurance_fields_image.json"
    }
    
    for name, path in possible_files.items():
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    json_files[name] = json.load(f)
            except Exception as e:
                json_files[name] = f"Error loading {path}: {str(e)}"
    
    return json_files

def main():
    """Main Streamlit application"""
    
    # Initialize session state
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = 1
    if 'uploaded_pdf' not in st.session_state:
        st.session_state.uploaded_pdf = None
    if 'processing_running' not in st.session_state:
        st.session_state.processing_running = False
    if 'total_pages' not in st.session_state:
        st.session_state.total_pages = 1
    
    # Header
    st.markdown('<h1 class="main-header">🏢 Insurance Document Processor</h1>', unsafe_allow_html=True)
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")
    
    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "Upload PDF Document",
        type=['pdf'],
        help="Upload an insurance document to process",
        key="pdf_uploader"
    )
    
    # Add clear file button if file is uploaded
    if uploaded_file is not None:
        st.sidebar.success(f"📄 **Current File:** {uploaded_file.name}")
        st.sidebar.info(f"**Size:** {len(uploaded_file.getvalue()) / 1024:.1f} KB")
        
        if st.sidebar.button("🗑️ Clear Current PDF", help="Remove current PDF to upload a new one"):
            # Clear all session state
            for key in list(st.session_state.keys()):
                if key.startswith(('pdf', 'uploaded', 'processing', 'selected', 'total', 'current')):
                    del st.session_state[key]
            st.rerun()
    
    # Clear session state if a new file is uploaded
    if uploaded_file is not None:
        # Check if this is a new file
        if (st.session_state.uploaded_pdf is None or 
            st.session_state.uploaded_pdf.name != uploaded_file.name or
            len(st.session_state.uploaded_pdf.getvalue()) != len(uploaded_file.getvalue())):
            
            # Clear all previous session state for new file
            st.session_state.uploaded_pdf = uploaded_file
            st.session_state.processing_complete = False
            st.session_state.selected_page = 1
            if 'pdf_images' in st.session_state:
                del st.session_state.pdf_images
            if 'total_pages' in st.session_state:
                del st.session_state.total_pages
            if 'current_pdf_name' in st.session_state:
                del st.session_state.current_pdf_name
            if 'pdf_images_path' in st.session_state:
                del st.session_state.pdf_images_path
        else:
            st.session_state.uploaded_pdf = uploaded_file
    
    # Script selection
    script_choice = st.sidebar.selectbox(
        "Choose Processing Script",
        [
            "OCR-based (main.py)",
            "Vision-based (main-vision.py)", 
            "Image-based (main-image.py)"
        ],
        help="Select which processing method to use"
    )
    
    # Cache option - DEFAULT TO FALSE
    use_cache = st.sidebar.checkbox(
        "Use Cache",
        value=False,
        help="Enable caching to speed up repeated processing"
    )
    
    # Add separator
    st.sidebar.markdown("---")
    
    # Add padding option - DEFAULT TO TRUE
    add_padding = st.sidebar.checkbox(
        "Add Padding Pages",
        value=True,
        help="Add context pages around relevant pages for better field extraction"
    )
    
    # Show current configuration
    st.sidebar.markdown("**Current Configuration:**")
    st.sidebar.markdown(f"- Cache: {'✅ Enabled' if use_cache else '❌ Disabled'}")
    st.sidebar.markdown(f"- Padding: {'✅ Enabled' if add_padding else '❌ Disabled'}")
    
    st.sidebar.markdown("---")
    
    # Processing button
    process_button = st.sidebar.button(
        "🚀 Start Processing",
        type="primary",
        disabled=(uploaded_file is None or st.session_state.processing_running)
    )
    
    # Main content area
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            
            # Display PDF as images with navigation
            total_pages = display_pdf_as_images(uploaded_file, st.session_state.selected_page)
            if total_pages > 0:
                st.session_state.total_pages = total_pages
        
        with col2:
            st.header("📊 Processing Results")
            
            # Use container with fixed height for scrolling
            with st.container(height=1000):
                if process_button:
                    st.session_state.processing_running = True
                    
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        temp_pdf_path = tmp_file.name
                    
                    try:
                        # Progress tracking
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Step 1: Initialize
                        progress_bar.progress(10)
                        status_text.text("🔄 Initializing processing...")
                        time.sleep(1)
                        
                        # Step 2: Processing
                        progress_bar.progress(30)
                        status_text.text("🤖 Processing document with AI...")
                        
                        # Get PDF images path if available
                        pdf_images_path = st.session_state.get('pdf_images_path', None)
                        
                        # Run the processing
                        success, result = run_processing_script_sync(script_choice, temp_pdf_path, use_cache, pdf_images_path, add_padding)
                        
                        if success:
                            progress_bar.progress(80)
                            status_text.text("📄 Extracting insurance fields...")
                            time.sleep(1)
                            
                            progress_bar.progress(100)
                            status_text.text("✅ Processing complete!")
                            st.session_state.processing_complete = True
                            
                            # Display total cost if available
                            if isinstance(result, (int, float)) and result > 0:
                                st.success(f"Document processed successfully! 💰 Total Cost: ${result:.6f}")
                            else:
                                st.success("Document processed successfully!")
                        else:
                            st.error(f"Processing failed: {result}")
                            
                    except Exception as e:
                        st.error(f"Unexpected error: {str(e)}")
                    finally:
                        # Clean up temporary file
                        if os.path.exists(temp_pdf_path):
                            os.unlink(temp_pdf_path)
                        st.session_state.processing_running = False
                
                # Display results if available
                json_results = load_json_results(script_choice)
                
                if json_results:
                    st.success("📄 Results loaded successfully!")
                    
                    # Display each insurance type
                    for insurance_type, insurance_data in json_results.items():
                        if isinstance(insurance_data, dict):
                            st.markdown(f"### 🏷️ {insurance_type}")
                            
                            # Check if this is the new structure with nested sections
                            if any(isinstance(v, dict) and ('value' in v or 'source' in v) for v in insurance_data.values()):
                                # Direct fields structure
                                for field_name, field_data in insurance_data.items():
                                    if isinstance(field_data, dict):
                                        display_field_value(field_name, field_data, uploaded_file)
                            else:
                                # Nested sections structure
                                for section_name, section_data in insurance_data.items():
                                    if isinstance(section_data, dict):
                                        display_insurance_section(section_name, section_data, uploaded_file)
                            
                            st.markdown("---")
                
                elif st.session_state.processing_complete:
                    st.warning("No results found. Please check if processing completed successfully.")
                else:
                    st.info("Upload a PDF and click 'Start Processing' to begin.")
    
    else:
        st.info("👆 Please upload a PDF document to get started.")
    

if __name__ == "__main__":
    main() 