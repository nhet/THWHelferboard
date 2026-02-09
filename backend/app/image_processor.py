"""Image processing and thumbnail generation for optimized web delivery."""

import os
import shutil
from pathlib import Path
from typing import Optional, List
import logging

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

logger = logging.getLogger(__name__)

# Thumbnail sizes: (width, height, name_suffix)
THUMBNAIL_SIZES = [
    (110, 110, "thumb-sm"),      # Helper cards on public index
    (220, 220, "thumb-md"),      # 2x resolution for high-DPI displays
    (165, 165, "thumb-detail"),  # Helper cards on detail page
    (330, 330, "thumb-detail-2x"),  # 2x for detail page
]

CAROUSEL_SIZE = (1000, None)  # Max 1000px wide, maintain aspect ratio


def get_thumbnail_paths(original_path: str, with_formats: List[str] = None) -> dict:
    """
    Returns dict of all expected thumbnail paths for a given original image.
    Only supports JPG/PNG for thumbnail generation (not SVG).
    
    Example:
        get_thumbnail_paths("uploads/photos/abc123.jpg")
        -> {
            "webp": ["uploads/photos/abc123-thumb-sm.webp", ...],
            "avif": ["uploads/photos/abc123-thumb-sm.avif", ...],
            "jpg": ["uploads/photos/abc123-thumb-sm.jpg", ...],
        }
    """
    if with_formats is None:
        with_formats = ["webp", "avif", "jpg"]
    
    path_obj = Path(original_path)
    stem = path_obj.stem  # filename without extension
    parent = path_obj.parent
    
    thumbs = {fmt: [] for fmt in with_formats}
    
    for width, height, suffix in THUMBNAIL_SIZES:
        for fmt in with_formats:
            thumb_name = f"{stem}-{suffix}.{fmt}"
            thumb_path = parent / thumb_name
            thumbs[fmt].append(str(thumb_path))
    
    return thumbs


def is_image_processable(file_path: Path) -> bool:
    """Check if a file can be processed with PIL (jpg, png, gif, webp, etc)."""
    processable_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}
    return file_path.suffix.lower() in processable_exts


def generate_thumbnails(original_path: Path, static_dir: Path, keep_original_format: bool = True) -> bool:
    """
    Generate thumbnails for the given image in multiple sizes and formats (webp, avif, jpg).
    
    Args:
        original_path: Full path to the original image file (relative to static_dir if relative)
        static_dir: Base static directory path
        keep_original_format: If True, also keep JPG/PNG version alongside WebP/AVIF
    
    Returns:
        True if thumbnails were generated successfully, False otherwise
    """
    if not HAS_PILLOW:
        logger.warning("Pillow not installed. Skipping thumbnail generation.")
        return False
    
    # Resolve to absolute path if needed
    if not original_path.is_absolute():
        original_path = static_dir / original_path
    
    if not original_path.exists():
        logger.error(f"Original image not found: {original_path}")
        return False
    
    if not is_image_processable(original_path):
        logger.warning(f"Image type not processable (e.g., SVG): {original_path}")
        return False
    
    try:
        with Image.open(original_path) as img:
            # Ensure RGBA or RGB for consistency
            if img.mode in ("RGBA", "LA", "P"):
                # Convert RGBA to RGB with white background for better compression
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "LA":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # Generate carousel-size version (if width > 1000px)
            img_carousel = img.copy()
            if img.width > 1000 or img.height > 1000:
                img_carousel.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
            
            carousel_path = original_path.parent / f"{original_path.stem}-carousel.webp"
            img_carousel.save(carousel_path, "WEBP", quality=85, method=6)
            logger.info(f"Generated carousel version: {carousel_path}")
            
            # Generate thumbnails
            for width, height, suffix in THUMBNAIL_SIZES:
                img_thumb = img.copy()
                img_thumb.thumbnail((width, height) if height else (width, width), Image.Resampling.LANCZOS)
                
                # WebP
                webp_path = original_path.parent / f"{original_path.stem}-{suffix}.webp"
                img_thumb.save(webp_path, "WEBP", quality=80, method=6)
                logger.info(f"Generated thumbnail: {webp_path}")
                
                # AVIF (fallback graceful if pillow-heif not available)
                try:
                    avif_path = original_path.parent / f"{original_path.stem}-{suffix}.avif"
                    img_thumb.save(avif_path, "AVIF", quality=75)
                    logger.info(f"Generated thumbnail: {avif_path}")
                except Exception as e:
                    logger.warning(f"Could not save AVIF (pillow-heif needed): {e}")
                
                # JPG (keep original format for fallback)
                if keep_original_format:
                    jpg_path = original_path.parent / f"{original_path.stem}-{suffix}.jpg"
                    img_thumb.save(jpg_path, "JPEG", quality=80, optimize=True)
                    logger.info(f"Generated thumbnail: {jpg_path}")
        
        logger.info(f"Successfully generated all thumbnails for: {original_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error generating thumbnails for {original_path}: {e}")
        return False


def delete_thumbnails(original_path: Path, static_dir: Path) -> bool:
    """
    Delete all thumbnail variants of an image.
    Also deletes carousel version if it exists.
    
    Args:
        original_path: Path relative to static_dir or absolute
        static_dir: Base static directory
    
    Returns:
        True if all deletions succeeded or no thumbnails found
    """
    if not original_path.is_absolute():
        original_path = static_dir / original_path
    
    if not original_path.exists():
        logger.warning(f"Original image not found for cleanup: {original_path}")
        return False
    
    stem = original_path.stem
    parent = original_path.parent
    
    deleted_count = 0
    
    # Delete carousel version
    carousel_path = parent / f"{stem}-carousel.webp"
    if carousel_path.exists():
        try:
            carousel_path.unlink()
            deleted_count += 1
            logger.info(f"Deleted carousel version: {carousel_path}")
        except Exception as e:
            logger.error(f"Error deleting carousel version: {e}")
    
    # Delete all thumbnail variants
    for width, height, suffix in THUMBNAIL_SIZES:
        for fmt in ["webp", "avif", "jpg"]:
            thumb_path = parent / f"{stem}-{suffix}.{fmt}"
            if thumb_path.exists():
                try:
                    thumb_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted thumbnail: {thumb_path}")
                except Exception as e:
                    logger.error(f"Error deleting thumbnail {thumb_path}: {e}")
    
    logger.info(f"Deleted {deleted_count} thumbnail variants for: {original_path}")
    return True


def delete_original_and_thumbnails(original_path: Path, static_dir: Path) -> bool:
    """
    Delete the original image and all its thumbnails.
    
    Args:
        original_path: Path relative to static_dir or absolute
        static_dir: Base static directory
    
    Returns:
        True if all deletions succeeded
    """
    if not original_path.is_absolute():
        original_path = static_dir / original_path
    
    success = True
    
    # Delete thumbnails first
    if not delete_thumbnails(original_path, static_dir):
        success = False
    
    # Delete original
    if original_path.exists():
        try:
            original_path.unlink()
            logger.info(f"Deleted original image: {original_path}")
        except Exception as e:
            logger.error(f"Error deleting original image: {e}")
            success = False
    
    return success
