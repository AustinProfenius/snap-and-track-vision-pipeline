"""
Image preprocessing module for optimal vision model performance.

Features:
- EXIF orientation correction
- Optimal resolution scaling (1024-1536px longest side)
- Quality-aware JPEG compression
- Multi-crop support for cluttered plates
"""
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image, ImageOps
import io


class ImagePreprocessor:
    """Handles image preprocessing for vision models."""

    def __init__(self,
                 target_size: int = 1536,
                 jpeg_quality: int = 95,
                 enable_multi_crop: bool = False):
        """
        Initialize image preprocessor.

        Args:
            target_size: Target size for longest edge (default: 1536px)
            jpeg_quality: JPEG compression quality 1-100 (default: 95)
            enable_multi_crop: Enable multi-crop for cluttered plates (default: False)
        """
        self.target_size = target_size
        self.jpeg_quality = jpeg_quality
        self.enable_multi_crop = enable_multi_crop

    def load_and_correct_orientation(self, image_path: Path) -> Image.Image:
        """
        Load image and apply EXIF orientation correction.

        Args:
            image_path: Path to image file

        Returns:
            PIL Image with corrected orientation
        """
        img = Image.open(image_path)

        # Apply EXIF orientation (handles phone camera rotation)
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed (handles RGBA, grayscale, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        return img

    def resize_to_optimal(self, img: Image.Image) -> Image.Image:
        """
        Resize image to optimal resolution for vision models.

        Maintains aspect ratio, resizes longest edge to target_size.
        Uses high-quality Lanczos resampling.

        Args:
            img: PIL Image

        Returns:
            Resized PIL Image
        """
        width, height = img.size
        longest = max(width, height)

        # Only resize if image is larger than target
        if longest > self.target_size:
            scale = self.target_size / longest
            new_width = int(width * scale)
            new_height = int(height * scale)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return img

    def optimize_jpeg(self, img: Image.Image) -> bytes:
        """
        Optimize image as JPEG with high quality.

        Args:
            img: PIL Image

        Returns:
            JPEG bytes
        """
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=self.jpeg_quality, optimize=True)
        return buffer.getvalue()

    def create_multi_crops(self, img: Image.Image) -> List[Image.Image]:
        """
        Create multiple crops for cluttered plates.

        Returns:
        - Full plate view
        - Top-left quadrant zoom
        - Top-right quadrant zoom
        - Bottom-left quadrant zoom
        - Bottom-right quadrant zoom

        Args:
            img: PIL Image

        Returns:
            List of cropped PIL Images
        """
        width, height = img.size

        crops = [img]  # Full plate

        # Create 4 overlapping quadrant zooms (60% of image each)
        crop_size_w = int(width * 0.6)
        crop_size_h = int(height * 0.6)

        # Top-left
        crops.append(img.crop((0, 0, crop_size_w, crop_size_h)))

        # Top-right
        crops.append(img.crop((width - crop_size_w, 0, width, crop_size_h)))

        # Bottom-left
        crops.append(img.crop((0, height - crop_size_h, crop_size_w, height)))

        # Bottom-right
        crops.append(img.crop((width - crop_size_w, height - crop_size_h, width, height)))

        return crops

    def preprocess(self, image_path: Path) -> Tuple[Image.Image, Optional[List[Image.Image]]]:
        """
        Complete preprocessing pipeline.

        Steps:
        1. Load and correct EXIF orientation
        2. Resize to optimal resolution
        3. Optionally create multi-crops

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (main_image, optional_crops)
        """
        # Load and correct orientation
        img = self.load_and_correct_orientation(image_path)

        # Resize to optimal
        img = self.resize_to_optimal(img)

        # Create multi-crops if enabled
        crops = None
        if self.enable_multi_crop:
            crops = self.create_multi_crops(img)
            # Resize each crop
            crops = [self.resize_to_optimal(crop) for crop in crops]

        return img, crops

    def preprocess_to_bytes(self, image_path: Path) -> Tuple[bytes, Optional[List[bytes]]]:
        """
        Preprocess image and return as JPEG bytes.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (main_image_bytes, optional_crop_bytes)
        """
        img, crops = self.preprocess(image_path)

        # Convert main image to bytes
        main_bytes = self.optimize_jpeg(img)

        # Convert crops to bytes
        crop_bytes = None
        if crops:
            crop_bytes = [self.optimize_jpeg(crop) for crop in crops]

        return main_bytes, crop_bytes


def preprocess_image_for_api(image_path: Path,
                             target_size: int = 1536,
                             jpeg_quality: int = 95) -> bytes:
    """
    Convenience function for single-image preprocessing.

    Args:
        image_path: Path to image file
        target_size: Target size for longest edge (default: 1536px)
        jpeg_quality: JPEG quality 1-100 (default: 95)

    Returns:
        Optimized JPEG bytes
    """
    preprocessor = ImagePreprocessor(target_size=target_size, jpeg_quality=jpeg_quality)
    img_bytes, _ = preprocessor.preprocess_to_bytes(image_path)
    return img_bytes
