from pathlib import Path
from typing import Union, Tuple, Optional
import numpy as np
import cv2
from PIL import Image

from backend.app.inference.schemas import ImageMetadata, PreprocessedInput

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

class Preprocessor:
    """
    Handles image loading, spatial metadata extraction, format conversions,
    and tensor normalization for Depth Anything V2 models.
    """
    def __init__(self, target_size: int = 518):
        # Target dimension must be divisible by ViT patch size 14
        assert target_size % 14 == 0, f"Target size {target_size} must be divisible by 14"
        self.target_size = target_size

    def load_image(self, input_source: Union[str, Path, np.ndarray]) -> Tuple[np.ndarray, ImageMetadata]:
        """
        Loads an optical image from a file path or array.
        Extracts geospatial tags if the source is a georeferenced GeoTIFF.
        Returns: (rgb_image_uint8, ImageMetadata)
        """
        if isinstance(input_source, (str, Path)):
            path = Path(input_source)
            if not path.exists():
                raise FileNotFoundError(f"Image source not found: {path}")

            # Try rasterio first to inspect geospatial metadata
            has_georef = False
            crs = None
            transform = None
            bounds = None
            nodata = None

            try:
                import rasterio
                with rasterio.open(path) as src:
                    if src.crs is not None:
                        has_georef = True
                        crs = str(src.crs)
                        transform = tuple(src.transform)
                        bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
                        nodata = src.nodata
                        
                    # Read RGB bands
                    if src.count >= 3:
                        rgb = src.read([1, 2, 3])  # Shape: (3, H, W)
                        rgb = np.transpose(rgb, (1, 2, 0))  # Shape: (H, W, 3)
                    elif src.count == 1:
                        gray = src.read(1)
                        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
                    else:
                        raise ValueError(f"Unsupported band count in raster: {src.count}")
                    
                    # Ensure uint8 [0, 255]
                    if rgb.dtype != np.uint8:
                        if rgb.max() > 0:
                            rgb = ((rgb - rgb.min()) / (rgb.max() - rgb.min()) * 255.0).astype(np.uint8)
                        else:
                            rgb = rgb.astype(np.uint8)

                    meta = ImageMetadata(
                        original_height=rgb.shape[0],
                        original_width=rgb.shape[1],
                        channels=3,
                        format=path.suffix.lower().lstrip('.'),
                        has_georeference=has_georef,
                        crs=crs,
                        transform=transform,
                        bounds=bounds,
                        nodata=nodata
                    )
                    return rgb, meta
            except Exception:
                # Fallback to standard Pillow loading if rasterio fails or for plain images
                pass

            with Image.open(path) as img:
                rgb_img = img.convert("RGB")
                arr = np.array(rgb_img, dtype=np.uint8)
                meta = ImageMetadata(
                    original_height=arr.shape[0],
                    original_width=arr.shape[1],
                    channels=3,
                    format=path.suffix.lower().lstrip('.'),
                    has_georeference=False
                )
                return arr, meta

        elif isinstance(input_source, np.ndarray):
            arr = input_source
            if arr.ndim == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
            elif arr.ndim == 3 and arr.shape[2] == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
            elif arr.ndim == 3 and arr.shape[2] == 1:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)

            if arr.dtype != np.uint8:
                arr = ((arr - arr.min()) / (arr.max() - arr.min() + 1e-6) * 255.0).astype(np.uint8)

            meta = ImageMetadata(
                original_height=arr.shape[0],
                original_width=arr.shape[1],
                channels=3,
                format="raw_numpy",
                has_georeference=False
            )
            return arr, meta
        else:
            raise TypeError(f"Unsupported input source type: {type(input_source)}")

    def preprocess(self, input_source: Union[str, Path, np.ndarray]) -> PreprocessedInput:
        """
        Loads the image, extracts metadata, resizes to model input dimension,
        and applies standard ImageNet normalization.
        Returns: PreprocessedInput with tensor of shape (1, 3, target_size, target_size).
        """
        rgb_img, metadata = self.load_image(input_source)
        orig_h, orig_w = rgb_img.shape[:2]

        # Resize to target dimension (518 x 518)
        resized = cv2.resize(rgb_img, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC)

        # Scale to [0.0, 1.0] and normalize with ImageNet statistics
        arr = resized.astype(np.float32) / 255.0
        normalized = (arr - IMAGENET_MEAN) / IMAGENET_STD

        # Transpose HWC -> CHW -> NCHW
        tensor = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]  # Shape: (1, 3, H, W)

        return PreprocessedInput(
            tensor=tensor.astype(np.float32),
            original_dimensions=(orig_h, orig_w),
            model_dimensions=(self.target_size, self.target_size),
            metadata=metadata
        )
