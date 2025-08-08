import os
import time
import psutil
import fitz  # PyMuPDF
import multiprocessing as mp
from typing import Literal
import base64

# mp.set_start_method("fork")         # on Linux/macOS; no-op on Windows

def render_range(args):
    idx, total_procs, pdf_path, zoom, outdir = args
    doc = fitz.open(pdf_path)
    seg = doc.page_count // total_procs + 1
    start = idx * seg
    end = min((idx + 1) * seg, doc.page_count)
    mat = fitz.Matrix(zoom, zoom)
    for i in range(start, end):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        pix.save(os.path.join(outdir, f"page_{i:04d}.png"))
    doc.close()

def pdf_to_image(pdf_path, return_type: Literal['local_path', 'base64','image_bytes'] = 'local_path', outdir='../pdf_images', zoom=2.0):
    os.makedirs(outdir, exist_ok=True)
    proc = psutil.Process()
    t0 = time.perf_counter()
    mem0 = psutil.virtual_memory().used
    cpu0 = sum(proc.cpu_times()[:2]); mem0 = psutil.virtual_memory().used

    cpus = mp.cpu_count()
    args = [(i, cpus, pdf_path, zoom, outdir) for i in range(cpus)]
    with mp.Pool(processes=cpus) as pool:
        pool.map(render_range, args)



    # Gather all image paths, sort by page number
    image_files = [os.path.join(outdir, fname) for fname in os.listdir(outdir) if fname.startswith("page_") and fname.endswith(".png")]
    image_files.sort()  # page_0000.png, page_0001.png, ...
    return_list = []
    if return_type == 'local_path':
        return_list= image_files
    elif return_type == 'base64':
        base64_list = []
        for img_path in image_files:
            with open(img_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
                base64_list.append(encoded)
        return_list= base64_list
        print("saved in ",outdir)
        # Remove all files in outdir, then remove the directory itself
        if os.path.exists(outdir):
            for fname in os.listdir(outdir):
                file_path = os.path.join(outdir, fname)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
            try:
                os.rmdir(outdir)
            except Exception as e:
                print(f"Failed to remove directory {outdir}. Reason: {e}")
    elif return_type == 'image_bytes':
        image_bytes_list = []
        for img_path in image_files:
            with open(img_path, "rb") as f:
                image_bytes_list.append(f.read())
        return_list= image_bytes_list
        if os.path.exists(outdir):
            for fname in os.listdir(outdir):
                file_path = os.path.join(outdir, fname)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
            try:
                os.rmdir(outdir)
            except Exception as e:
                print(f"Failed to remove directory {outdir}. Reason: {e}")
    else:
        raise ValueError("return_type must be 'local_path' or 'base64'")

    wall = time.perf_counter() - t0
    cpu  = sum(proc.cpu_times()[:2]) - cpu0
    ram  = (psutil.virtual_memory().used - mem0) / (1024**2)
    print(f"[PyMuPDF] wall={wall:.2f}s  CPU-sec={cpu:.2f}s  ΔRAM={ram:.1f} MB")

    return return_list


if __name__ == "__main__":
    pdf_to_image("input.pdf",'local_path')