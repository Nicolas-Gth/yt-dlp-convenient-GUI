"""
Image processing utilities for thumbnails and icons.
"""
import urllib.request
from io import BytesIO
from PIL import Image, ImageTk
from typing import Optional, Tuple

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
        
        if is_music:
            # Crop to square for music videos
            width, height = im.size
            left = int((width - height) / 2)
            top = 0
            right = width - int((width - height) / 2)
            bottom = height
            im = im.crop((left, top, right, bottom))
            # Use square size for music
            size = (60, 60)
        
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

        # Crop to square
        width, height = im.size
        left = int((width - height) / 2)
        top = 0
        right = width - int((width - height) / 2)
        bottom = height
        album_im = im.crop((left, top, right, bottom))
        
        # Convert to JPEG bytes
        with BytesIO() as output:
            album_im.save(output, format="JPEG")
            return output.getvalue()
            
    except Exception as e:
        print(f"Warning: Could not process album cover: {e}")
        return None
