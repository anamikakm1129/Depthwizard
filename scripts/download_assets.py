import sys
from pathlib import Path
from huggingface_hub import hf_hub_download
import urllib.request

MODELS_DIR = Path(__file__).resolve().parent.parent / "backend" / "models"
DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "data"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

def download_model():
    print("=== 1. Acquiring Depth Anything V2 Small INT8 Model ===")
    repo_id = "onnx-community/depth-anything-v2-small"
    filename = "onnx/model_int8.onnx"
    target_path = MODELS_DIR / "depth_anything_v2_vits_int8.onnx"
    
    if target_path.exists():
        print(f"Model already exists at: {target_path} ({target_path.stat().st_size / (1024*1024):.2f} MB)")
        return target_path
        
    print(f"Downloading {filename} from Hugging Face Hub ({repo_id})...")
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=MODELS_DIR,
        local_dir_use_symlinks=False
    )
    # Rename to clean target name if downloaded into subfolder
    downloaded = Path(downloaded_path)
    if downloaded != target_path:
        downloaded.replace(target_path)
        # Clean empty subfolder if created
        parent_onnx = MODELS_DIR / "onnx"
        if parent_onnx.exists() and not any(parent_onnx.iterdir()):
            parent_onnx.rmdir()
            
    print(f"Successfully downloaded to: {target_path}")
    print(f"File size: {target_path.stat().st_size / (1024*1024):.2f} MB")
    return target_path

def download_sample_images():
    print("\n=== 2. Acquiring Real Sample Imagery ===")
    # Verified open-access sample orthophoto/aerial crop from OpenDroneMap / rasterio test repositories
    aerial_url = "https://raw.githubusercontent.com/cogeotiff/rio-tiler/master/tests/fixtures/cog.tif"
    aerial_target = DATA_DIR / "sample_aerial.tif"
    
    geotiff_url = "https://raw.githubusercontent.com/rasterio/rasterio/main/tests/data/RGB.byte.tif"
    geotiff_target = DATA_DIR / "sample_geotiff.tif"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    if not aerial_target.exists():
        print(f"Downloading verified sample aerial raster from {aerial_url}...")
        req = urllib.request.Request(aerial_url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(aerial_target, "wb") as f:
            f.write(resp.read())
        print(f"Saved sample aerial raster: {aerial_target} ({aerial_target.stat().st_size / 1024:.1f} KB)")
    else:
        print(f"Sample aerial raster exists: {aerial_target}")

    if not geotiff_target.exists():
        print(f"Downloading verified sample GeoTIFF from {geotiff_url}...")
        req = urllib.request.Request(geotiff_url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(geotiff_target, "wb") as f:
            f.write(resp.read())
        print(f"Saved GeoTIFF: {geotiff_target} ({geotiff_target.stat().st_size / 1024:.1f} KB)")
    else:
        print(f"Sample GeoTIFF exists: {geotiff_target}")

if __name__ == "__main__":
    try:
        download_model()
        download_sample_images()
        print("\nAll Phase 1 assets acquired successfully.")
    except Exception as e:
        print(f"\nERROR during asset acquisition: {e}", file=sys.stderr)
        sys.exit(1)
