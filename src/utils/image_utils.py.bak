"""
Image processing utilities for thumbnails and icons.
"""
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk
from typing import Optional, Tuple


def _crop_to_square_removing_bars(im: Image.Image) -> Image.Image:
    """
    Remove dark bars (black or near-black) from the edges of an image,
    then center-crop the remaining content to a square.
    
    Uses PIL's point() + getbbox() for robust detection that handles
    gradients, compression artifacts, and non-pure-black bars.
    """
    width, height = im.size
    
    # Convert to grayscale, then threshold: any pixel with brightness > 30
    # is considered "content". This is generous enough to catch dark gradients
    # that YouTube Music uses around album art.
    gray = im.convert('L')
    # Create binary mask: 0 for dark pixels, 255 for bright ones
    threshold = 30
    binary = gray.point(lambda p: 255 if p > threshold else 0)
    
    # getbbox() returns the bounding box of non-zero pixels: (left, top, right, bottom)
    bbox = binary.getbbox()
    
    if bbox is None:
        # Entire image is dark, just center-crop
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        return im.crop((left, top, left + side, top + side))
    
    bleft, btop, bright, bbottom = bbox
    
    # Only crop if bars are significant (>5% of dimension on at least one side)
    has_left_bar = bleft > width * 0.05
    has_right_bar = (width - bright) > width * 0.05
    has_top_bar = btop > height * 0.05
    has_bottom_bar = (height - bbottom) > height * 0.05
    
    if has_left_bar or has_right_bar or has_top_bar or has_bottom_bar:
        im = im.crop(bbox)
    
    # Center-crop to square
    w, h = im.size
    side = min(w, h)
    crop_left = (w - side) // 2
    crop_top = (h - side) // 2
    return im.crop((crop_left, crop_top, crop_left + side, crop_top + side))


def _has_dark_bars(im: Image.Image) -> bool:
    """
    Quickly check if an image has significant dark bars on any side.
    Uses PIL's point() + getbbox() for reliable detection.
    """
    width, height = im.size
    gray = im.convert('L')
    binary = gray.point(lambda p: 255 if p > 30 else 0)
    bbox = binary.getbbox()
    
    if bbox is None:
        return False
    
    bleft, btop, bright, bbottom = bbox
    # Check if any side has a bar > 5% of the dimension
    return (bleft > width * 0.05 or
            (width - bright) > width * 0.05 or
            btop > height * 0.05 or
            (height - bbottom) > height * 0.05)


def load_thumbnail(thumbnail_url: str, size: Tuple[int, int] = (100, 60), is_music: bool = False) -> Optional[Image.Image]:
    """
    Load and process a thumbnail image from a URL.
    
    Args:
        thumbnail_url: URL of the thumbnail image
        size: Target size for the thumbnail (width, height)
        is_music: Whether to crop the image to square (for music videos)
    
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
        
        # Crop to square for music content (removes black bars around album art)
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

def load_icon(icon_path: str, root_window) -> bool:
    """
    Load and set the application icon.
    
    Args:
        icon_path: Path to the icon file
        root_window: Tkinter root window
    
    Returns:
        True if icon was set successfully, False otherwise
    """
    try:
        root_window.iconbitmap(icon_path)
        return True
    except Exception:
        # If .ico doesn't work, try to use it as a PhotoImage instead
        try:
            icon_image = Image.open(icon_path)
            icon_photo = ImageTk.PhotoImage(icon_image)
            root_window.iconphoto(False, icon_photo)
            return True
        except Exception:
            # If all else fails, just continue without an icon
            return False

def crop_album_cover(thumbnail_url: str) -> Optional[bytes]:
    """
    Download and crop thumbnail for use as album cover.
    
    Args:
        thumbnail_url: URL of the thumbnail
    
    Returns:
        JPEG image data as bytes, or None if processing fails
    """
    try:
        u = urllib.request.urlopen(thumbnail_url)
        raw_data = u.read()
        u.close()
        im = Image.open(BytesIO(raw_data))

        # Smart crop: remove dark bars then crop to square
        album_im = _crop_to_square_removing_bars(im)
        
        # Convert RGBA/P → RGB (JPEG doesn't support transparency)
        if album_im.mode in ('RGBA', 'P', 'LA'):
            album_im = album_im.convert('RGB')
        
        # Convert to JPEG bytes
        with BytesIO() as output:
            album_im.save(output, format="JPEG")
            return output.getvalue()
            
    except Exception as e:
        print(f"Warning: Could not process album cover: {e}")
        return None
