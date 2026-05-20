"""
Image processing utilities for thumbnails and icons.
"""
import urllib.request
from io import BytesIO
from PIL import Image
from typing import Optional, Tuple


def _crop_to_square_removing_bars(im: Image.Image) -> Image.Image:
    """
    Remove dark bars (black or near-black) from the edges of an image,
    then center-crop the remaining content to a square.
    
    Uses PIL's point() + getbbox() for robust detection that handles
    gradients, compression artifacts, and non-pure-black bars.
    """
    width, height = im.size
    
    gray = im.convert('L')
    threshold = 30
    binary = gray.point(lambda p: 255 if p > threshold else 0)
    
    bbox = binary.getbbox()
    
    if bbox is None:
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        return im.crop((left, top, left + side, top + side))
    
    bleft, btop, bright, bbottom = bbox
    
    has_left_bar = bleft > width * 0.05
    has_right_bar = (width - bright) > width * 0.05
    has_top_bar = btop > height * 0.05
    has_bottom_bar = (height - bbottom) > height * 0.05
    
    if has_left_bar or has_right_bar or has_top_bar or has_bottom_bar:
        im = im.crop(bbox)
    
    w, h = im.size
    side = min(w, h)
    crop_left = (w - side) // 2
    crop_top = (h - side) // 2
    return im.crop((crop_left, crop_top, crop_left + side, crop_top + side))


def _has_dark_bars(im: Image.Image) -> bool:
    """
    Quickly check if an image has significant dark bars on any side.
    """
    width, height = im.size
    gray = im.convert('L')
    binary = gray.point(lambda p: 255 if p > 30 else 0)
    bbox = binary.getbbox()
    
    if bbox is None:
        return False
    
    bleft, btop, bright, bbottom = bbox
    return (bleft > width * 0.05 or
            (width - bright) > width * 0.05 or
            btop > height * 0.05 or
            (height - bbottom) > height * 0.05)


def load_thumbnail(thumbnail_url: str, size: Tuple[int, int] = (100, 60), is_music: bool = False) -> Optional[Image.Image]:
    """
    Load and process a thumbnail image from a URL.
    
    Returns:
        PIL Image object or None if loading fails
    """
    if not thumbnail_url:
        return create_default_thumbnail(size)
    
    try:
        u = urllib.request.urlopen(thumbnail_url)
        raw_data = u.read()
        u.close()
        im = Image.open(BytesIO(raw_data))
        
        if is_music:
            im = _crop_to_square_removing_bars(im)
        
        im.thumbnail(size)
        return im
        
    except Exception as e:
        print(f"Could not load thumbnail: {e}")
        return create_default_thumbnail(size)

def create_default_thumbnail(size: Tuple[int, int] = (100, 60)) -> Image.Image:
    """Create a default gray thumbnail image."""
    return Image.new('RGB', size, color='gray')

def load_icon(icon_path: str, root_window=None) -> bool:
    """
    Load and set the application icon.
    This is now handled by PySide6's QIcon in window_view.py.
    Kept for backward compatibility.
    """
    return True

def crop_album_cover(thumbnail_url: str, force_square: bool = True) -> Optional[bytes]:
    """
    Download and crop thumbnail for use as album cover.

    Args:
        thumbnail_url: URL of the thumbnail image
        force_square: If True (default), crop to a square. If False, keep
                      the original aspect ratio (useful for video covers).

    Returns:
        JPEG image data as bytes, or None if processing fails
    """
    try:
        u = urllib.request.urlopen(thumbnail_url)
        raw_data = u.read()
        u.close()
        im = Image.open(BytesIO(raw_data))

        if force_square:
            album_im = _crop_to_square_removing_bars(im)
        else:
            album_im = im

        if album_im.mode in ('RGBA', 'P', 'LA'):
            album_im = album_im.convert('RGB')

        with BytesIO() as output:
            album_im.save(output, format="JPEG")
            return output.getvalue()

    except Exception as e:
        print(f"Warning: Could not process album cover: {e}")
        return None
