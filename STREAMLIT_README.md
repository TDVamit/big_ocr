# 🏢 Insurance Document Processor - Streamlit Frontend

A comprehensive web interface for processing insurance documents with AI-powered field extraction.

## ✨ Features

- **📄 PDF Upload**: Drag and drop PDF documents for processing
- **🔄 Multiple Processing Methods**: Choose between OCR, Vision, or Image-based processing
- **⚡ Cache Control**: Enable/disable caching for faster repeated processing
- **📊 Real-time Progress**: See processing steps in real-time
- **🖼️ Interactive PDF Viewer**: View PDF with page navigation
- **🎯 Smart Field Display**: Extracted fields shown in user-friendly format
- **🔗 Clickable Source Pages**: Click page numbers to jump to specific PDF pages
- **📱 Responsive Design**: Works on desktop and mobile devices
- **🔍 Raw JSON Access**: View raw extraction results for debugging

## 🚀 Quick Start

### Method 1: Using the Launcher Script
```bash
python run_streamlit.py
```

### Method 2: Manual Setup
```bash
# Install requirements
pip install -r streamlit_requirements.txt

# Run Streamlit
streamlit run streamlit-frontend.py
```

### Method 3: Direct Command
```bash
python -m streamlit run streamlit-frontend.py --server.port 8501
```

## 📋 Requirements

- Python 3.8+
- All dependencies from `streamlit_requirements.txt`
- Valid OpenAI API key (set in environment)
- Google Cloud Vision API credentials (for OCR processing)

## 🎮 How to Use

### 1. **Upload Document**
   - Click "Upload PDF Document" in the sidebar
   - Select your insurance document (PDF format)

### 2. **Choose Processing Method**
   - **OCR-based (main.py)**: Google Cloud Vision OCR + AI field extraction
   - **Vision-based (main-vision.py)**: OpenAI Vision API for everything
   - **Image-based (main-image.py)**: OCR + Image-based field extraction

### 3. **Configure Settings**
   - ✅ **Use Cache**: Enable for faster repeated processing
   - ❌ **Disable Cache**: Force fresh processing

### 4. **Process Document**
   - Click "🚀 Start Processing"
   - Watch the progress bar and status updates
   - Wait for completion

### 5. **View Results**
   - **Left Panel**: PDF viewer with page navigation
   - **Right Panel**: Extracted insurance fields in organized sections
   - **Bottom**: Raw JSON results for technical review

## 🎯 Interactive Features

### **📄 PDF Navigation**
- Use the page number input to jump to specific pages
- Click on source page numbers in field results to navigate instantly

### **📋 Field Display**
Each extracted field shows:
- **Value**: The extracted information
- **Confidence**: AI confidence score (color-coded)
  - 🟢 **Green**: High confidence (≥80%)
  - 🟡 **Yellow**: Medium confidence (50-79%)
  - 🔴 **Red**: Low confidence (<50%)
- **Source Pages**: Clickable page numbers

### **🔍 Organized Sections**
Results are organized by insurance type:
- **Property Insurance**: Building coverage, limits, deductibles
- **Auto Insurance**: Vehicle details, coverage, drivers
- **Professional Liability**: E&O coverage, limits, operations
- **Cyber Insurance**: Network security, privacy coverage
- **Workers Compensation**: Class codes, payroll, coverage

## 📁 File Structure

```
├── streamlit-frontend.py          # Main Streamlit application
├── run_streamlit.py              # Launcher script
├── streamlit_requirements.txt    # Python dependencies
├── main.py                       # OCR-based processing
├── main-vision.py               # Vision-based processing  
├── main-image.py                # Image-based processing
├── json/                        # Results directory
│   ├── ocr_results.json         # OCR cache
│   ├── vision_results.json      # Vision cache
│   ├── extracted_insurance_fields.json      # OCR/Vision results
│   └── extracted_insurance_fields_image.json # Image results
└── pdf_images/                  # Image cache directory
```

## 🎨 User Interface

### **Sidebar Configuration**
- File uploader
- Processing method selection
- Cache toggle
- Start processing button

### **Main Content Area**
- **Left Column**: PDF viewer with navigation
- **Right Column**: Processing results and status

### **Results Display**
- Scrollable field sections
- Color-coded confidence indicators
- Interactive page navigation buttons
- Expandable/collapsible sections

## ⚙️ Configuration Options

### **Processing Scripts**
- **OCR-based**: Best for text-heavy documents
- **Vision-based**: Best for mixed content (text + images)
- **Image-based**: Best for form-like documents

### **Cache Settings**
- **Enabled**: Faster processing, uses previous results
- **Disabled**: Always fresh processing, slower but current

## 🔧 Troubleshooting

### **PDF Not Displaying**
- Try a different browser (Chrome/Firefox recommended)
- Check if PDF is not corrupted
- Ensure PDF is not password-protected

### **Processing Fails**
- Check API keys are set correctly
- Verify internet connection
- Check console for error messages

### **No Results Showing**
- Ensure processing completed successfully
- Check if JSON files exist in `/json` folder
- Try processing with cache disabled

### **Slow Performance**
- Enable cache for repeated processing
- Check system resources
- Try smaller PDF files

## 🚀 Advanced Usage

### **Command Line Arguments**
```bash
# Custom port
streamlit run streamlit-frontend.py --server.port 8080

# External access
streamlit run streamlit-frontend.py --server.address 0.0.0.0

# Debug mode
streamlit run streamlit-frontend.py --logger.level debug
```

### **Environment Variables**
```bash
export OPENAI_API_KEY="your-openai-key"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
```

## 📊 Expected Output

The interface will display:
1. **Processing Progress**: Real-time status updates
2. **Organized Results**: Fields grouped by insurance type
3. **Interactive Elements**: Clickable page references
4. **Raw Data Access**: Complete JSON for debugging

## 🆘 Support

If you encounter issues:
1. Check the console for error messages
2. Verify all dependencies are installed
3. Ensure API credentials are configured
4. Try with a different PDF document
5. Check the troubleshooting section above

---

**🎉 Enjoy processing insurance documents with AI!** 