from tkinter import*
from tkinter import filedialog
import tkinter.ttk as ttk
from ttkthemes import ThemedTk
from io import BytesIO
from PIL import Image, ImageTk
import urllib.request
import yt_dlp
import datetime
import threading
from plyer import notification
import os
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import io
import re

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Build the path to the icon file relative to the script location
icon_path = os.path.join(script_dir, '..', 'assets', 'youtube-icon.ico')

root = ThemedTk(theme="equilux")
# Try to set the icon, but continue if it fails (common on Linux)
try:
    root.iconbitmap(icon_path)
except Exception:
    # If .ico doesn't work, try to use it as a PhotoImage instead
    try:
        icon_image = Image.open(icon_path)
        icon_photo = ImageTk.PhotoImage(icon_image)
        root.iconphoto(False, icon_photo)
    except Exception:
        # If all else fails, just continue without an icon
        pass

# Configure cross-platform font settings
import tkinter.font as tkFont

# Define consistent fonts for cross-platform compatibility
if os.name == 'nt':  # Windows
    default_font = ('Segoe UI', 9)
    title_font = ('Segoe UI', 10, 'bold')
else:  # Linux/Unix
    default_font = ('Liberation Sans', 9)
    title_font = ('Liberation Sans', 10, 'bold')

# Apply the default font
root.option_add('*Font', default_font)

# Configure ttk styles for consistency
style = ttk.Style()
style.configure('TLabel', font=default_font)
style.configure('TButton', font=default_font)
style.configure('TEntry', font=default_font)
style.configure('TCombobox', font=default_font)

def create_label(parent, text="", **kwargs):
    """Create a label with consistent font styling"""
    return ttk.Label(parent, text=text, font=default_font, **kwargs)

def create_button(parent, text="", **kwargs):
    """Create a button with consistent font styling"""
    return ttk.Button(parent, text=text, **kwargs)

root.title("yt-dlp Convenient GUI [v1.5] - Made by Nicolas-Gth")
# Start with base size that will be adjusted later
root.geometry("466x250")
root.minsize(466, 250)  # Set minimum size
root.configure(bg='#454746')
# Allow resizing to accommodate different font sizes
root.resizable(True, True)
is_verbose = True

# Build the path to ffmpeg relative to the script location (cross-platform)
if os.name == 'nt':  # Windows
    ffmpeg_dir = os.path.join(script_dir, '..', 'ffmpeg', 'bin')
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
    ffmpeg_path = ffmpeg_dir
else:  # Linux/Unix - assume ffmpeg is installed system-wide
    # Check if ffmpeg is available in system PATH
    import shutil
    ffmpeg_executable = shutil.which('ffmpeg')
    if ffmpeg_executable is None:
        print("Warning: ffmpeg not found in system PATH. Please install ffmpeg.")
        print("  Ubuntu/Debian: sudo apt install ffmpeg")
        print("  Fedora: sudo dnf install ffmpeg")
        print("  Arch: sudo pacman -S ffmpeg")
        ffmpeg_path = None  # Will cause yt-dlp to skip ffmpeg-dependent features
    else:
        ffmpeg_path = os.path.dirname(ffmpeg_executable)  # Use the directory containing ffmpeg
        print(f"Found ffmpeg at: {ffmpeg_executable}")

folder_path = StringVar()

def getFileFormat(number):
    match number:
        case 1:
            return "mp3"
        case 2:
            return "mp4"

def store(*CurrentSong):
	store.CurrentSong = CurrentSong or store.CurrentSong
	return store.CurrentSong[0]
CurrentSong = 0
store(CurrentSong)

def store2(*PreviousSong):
	store2.PreviousSong = PreviousSong or store2.PreviousSong
	return store2.PreviousSong[0]
PreviousSong = -1
store2(PreviousSong)

def browse_button():
    global folder_path
    filename = filedialog.askdirectory()
    folder_path.set(filename)

class MyCustomPP(yt_dlp.postprocessor.PostProcessor):
    def run(self, video_infos):

        file_format = getFileFormat(radio_button_format.get())
        file_path = f"{Entry2.get()}/{video_infos['title']}.{file_format}"

        # Check if the file actually exists (conversion might have failed)
        if not os.path.exists(file_path):
            print(f"Warning: File {file_path} not found. Conversion may have failed.")
            return [], video_infos

        # Add metadatas to the file
        try:
            artist_name = video_infos['artists'][0]
        except KeyError:
            artist_name = video_infos['uploader'].replace(" - Topic", "")
        
        if file_format == "mp3":
            try:
                metadatas = MP3(file_path, ID3=EasyID3)
                metadatas['artist'] = artist_name
                try:
                    album_name = video_infos['album']
                    metadatas['album'] = album_name
                except KeyError:
                    pass

                metadatas.save()
            except Exception as e:
                print(f"Warning: Could not add metadata to MP3 file: {e}")

        
        # Rename and sanitize the file name
        new_file_path = f"{Entry2.get()}/{re.sub(r'[!?:#%&{}<>|*/$@]', '', artist_name)} - {re.sub(r'[!?:#%&{}<>|*/$@]', '', video_infos['title'])}.{file_format}"
        try:
            os.rename(file_path, new_file_path)
            file_path = new_file_path
        except Exception as e:
            print(f"Warning: Could not rename file: {e}")
        
        if file_format == "mp3" and os.path.exists(file_path):
            # Downloads thumbnail image and sets it as the album cover
            try:
                u = urllib.request.urlopen(video_infos['thumbnail'])
                raw_data = u.read()
                u.close()
                im = Image.open(BytesIO(raw_data))

                width, height = im.size
                left = int((width - height)/2)
                top = 0
                right = width - int((width - height)/2)
                bottom = height
                album_im = im.crop((left, top, right, bottom))
                
                audio = ID3(file_path)
                with io.BytesIO() as output:
                    album_im.save(output, format="JPEG")
                    data = output.getvalue()
                with io.BytesIO(data) as albumart:
                    audio['APIC'] = APIC(encoding=0, mime='image/jpeg', type=3, desc=u'Cover', data=albumart.read())
                audio.save()
            except Exception as e:
                print(f"Warning: Could not add album cover to MP3: {e}")


        return [], video_infos


def convert():
    url = Entry1.get()
    directory = Entry2.get() + '/%(title)s.%(ext)s'
    global noplaylist
    noplaylist = radio_button_playlist.get()
    file_format = getFileFormat(radio_button_format.get())

    if noplaylist == True:
        playlist_start = 1
        playlist_end = 1
        Button2.configure(text="        Fetching video infos…        ")
    else:
        playlist_start = int(Entry3.get())
        playlist_end = int(Entry4.get())
        global playlist_length
        playlist_length = playlist_end - playlist_start
        Button2.configure(text="       Fetching playlist infos…      ")

    if file_format == "mp3":
        concatenated_bitrate = clicked.get()
        bitrate = concatenated_bitrate.split("Kbps")[0]
        format = 'bestaudio/best'
        
        # Base options
        ydl_opts = {
            'verbose': is_verbose, 
            'no-part': True,
            'ignoreerrors': True, 
            'quiet': True, 
            'extractor_args':{'youtubetab': {'skip':['authcheck']}}, 
            "external_downloader_args": ['-loglevel', 'panic'],
            'format': format,
            'outtmpl': directory,
            'noplaylist': noplaylist,
            'progress_hooks': [my_hook], 
            'playliststart': playlist_start, 
            'playlistend': playlist_end
        }
        
        # Add ffmpeg options only if ffmpeg is available
        if ffmpeg_path is not None:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['postprocessors'] = [
                {'key':'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': bitrate},
                {'key': 'FFmpegMetadata', 'add_metadata': True}
            ]
        else:
            print("Warning: MP3 conversion disabled - ffmpeg not found")
            # Just download the best audio format available
            ydl_opts['format'] = 'bestaudio'

    elif file_format == "mp4":
        concatenated_quality = clicked2.get()
        quality = concatenated_quality.split("p")[0]
        format = 'bestvideo[height<='+ quality +'][vbr<=12000][ext=mp4]+bestaudio[ext=m4a]/best[vbr<=12000][ext=mp4]/best'
        
        # Base options
        ydl_opts = {
            'verbose': is_verbose,
            'no-part': True,
            'ignoreerrors': True,
            'quiet': True,
            'extractor_args':{'youtubetab': {'skip':['authcheck']}}, 
            "external_downloader_args": ['-loglevel', 'panic'],
            'format': format,
            'outtmpl': directory,
            'noplaylist': noplaylist,
            'progress_hooks': [my_hook], 
            'playliststart': playlist_start, 
            'playlistend': playlist_end
        }
        
        # Add ffmpeg options only if ffmpeg is available
        if ffmpeg_path is not None:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            ydl_opts['postprocessors'] = [{'key':'FFmpegVideoConvertor','preferedformat': 'mp4'}]
        else:
            print("Warning: MP4 conversion disabled - ffmpeg not found")

    global video_infos
    try:
        #'writepages': True, 'verbose': True, 'cookiefile' : 'cookies.txt'
        video_infos = yt_dlp.YoutubeDL({'verbose': is_verbose, 'quiet': True,'ignoreerrors': True, 'extractor_args':{'youtubetab': {'skip':['authcheck']}},"external_downloader_args": ['-loglevel', 'panic'], 'simulate': True, 'cachedir': False,'noplaylist': noplaylist, 'playliststart': playlist_start, 'playlistend': playlist_end}).extract_info(url, download=False)

    except yt_dlp.utils.DownloadError as error:
        FetchingErrorStatus = True

        while FetchingErrorStatus == True:
            print("There was a problem during the fetching, automatically restarting!")
            try:
                video_infos = yt_dlp.YoutubeDL({'verbose': is_verbose, 'quiet': True,'ignoreerrors': True,'extractor_args':{'youtubetab': {'skip':['authcheck']}}, "external_downloader_args": ['-loglevel', 'panic'], 'simulate': True, 'cachedir': False,'noplaylist': noplaylist, 'playliststart': playlist_start, 'playlistend': playlist_end}).extract_info(url, download=False)
                FetchingErrorStatus = False
            except yt_dlp.utils.DownloadError as error:
                FetchingErrorStatus = True

    # Check if video_infos was successfully retrieved
    if video_infos is None:
        print("Error: Could not retrieve video information. Please check the URL.")
        Button2.configure(text="      Convert      ")
        return

    Button2.destroy()

    frameProgress = LabelFrame(root, bg='#454746', border = 0)
    frameProgress.grid(sticky = W, row=5, column=0)
    global My_progress
    My_progress = ttk.Progressbar(frameProgress, orient = HORIZONTAL, length = 316, mode = 'determinate')
    My_progress.grid(sticky = W, row=2, column=0, pady = 0, padx = 106)

    LabelMy_progress = ttk.Label(frameProgress, text = "Video progress :", anchor="w", justify = "left")
    LabelMy_progress.grid(sticky = W, row=2, column=0, pady = 0, padx = 7)

    if noplaylist == False:
        adjust_window_size(base_height=PLATFORM_SCALE['height_base'], extra_height=135)
        global Total_progress
        Total_progress = ttk.Progressbar(frameProgress, orient = HORIZONTAL, length = 316, mode = 'determinate')
        Total_progress.grid(sticky = W, row=3, column=0, pady = 0, padx = 106)

        LabelTotal_progress = ttk.Label(frameProgress, text = "Total progress :", anchor="w", justify = "left")
        LabelTotal_progress.grid(sticky = W, row=3, column=0, pady = 0, padx = 7)

        global LabelTotalProgress
        LabelTotalProgress = ttk.Label(frameProgress, text = " 0.0%", anchor="w", justify = "left")
        LabelTotalProgress.grid(sticky = W, row=3, column=0, pady = 10, padx = 424)

        # Safely access playlist information
        if 'entries' in video_infos and len(video_infos['entries']) > 0:
            thumbnail_url = video_infos['entries'][0].get('thumbnail', '')
            title = video_infos['entries'][0].get('title', 'Unknown')
            uploader = video_infos['entries'][0].get('uploader', 'Unknown')
            duration = video_infos['entries'][0].get('duration', 0)
            playlist_title = video_infos.get('title', 'Unknown Playlist')
            
            info_str = f"Title : \"{title}\"\nChannel : \"{uploader}\"\nDuration : {str(datetime.timedelta(seconds=int(duration)))}"
            songname_str = f"Downloading video 1 of {playlist_length+1} from the playlist \"{playlist_title}\""
            NotificationText = f"Playlist \"{playlist_title}\""
        else:
            print("Error: No entries found in playlist")
            Button2.configure(text="      Convert      ")
            return
    else:
        adjust_window_size(base_height=PLATFORM_SCALE['height_base'], extra_height=100)
        # Safely access single video information
        thumbnail_url = video_infos.get('thumbnail', '')
        title = video_infos.get('title', 'Unknown')
        uploader = video_infos.get('uploader', 'Unknown').replace(' - Topic', '')
        duration = video_infos.get('duration', 0)
        
        info_str = f"Title : \"{title}\"\nChannel : \"{uploader}\"\nDuration : {str(datetime.timedelta(seconds=int(duration)))}"
        songname_str = f"Downloading \"{title}\""
        NotificationText = f"Video \"{title}\""

    # Only try to load thumbnail if URL is available
    if thumbnail_url:
        try:
            u = urllib.request.urlopen(thumbnail_url)
            raw_data = u.read()
            u.close()
            im = Image.open(BytesIO(raw_data))
        except Exception as e:
            print(f"Could not load thumbnail: {e}")
            # Create a default image if thumbnail fails
            im = Image.new('RGB', (100, 60), color='gray')
    else:
        # Create a default image if no thumbnail URL
        im = Image.new('RGB', (100, 60), color='gray')
    thumbnail_margin = 74
    if noplaylist == False:
        # Safely check for categories in playlist entries
        try:
            current_entry = video_infos['entries'][store()]
            categories = current_entry.get('categories', [])
            if 'Music' in categories:
                width, height = im.size
                left = int((width - height)/2)
                top = 0
                right = width - int((width - height)/2)
                bottom = height
                im = im.crop((left, top, right, bottom))
                im.thumbnail((60, 60))
            else:
                im.thumbnail((100, 60))
                thumbnail_margin += 40
        except (KeyError, IndexError, TypeError):
            # Default thumbnail size if category check fails
            im.thumbnail((100, 60))
            thumbnail_margin += 40

    elif noplaylist == True:
        # Safely check for categories in single video
        try:
            categories = video_infos.get('categories', [])
            if 'Music' in categories:
                width, height = im.size
                left = int((width - height)/2)
                top = 0
                right = width - int((width - height)/2)
                bottom = height
                im = im.crop((left, top, right, bottom))
                im.thumbnail((60, 60))
            else:
                im.thumbnail((100, 60))
                thumbnail_margin += 40
        except (KeyError, TypeError):
            # Default thumbnail size if category check fails
            im.thumbnail((100, 60))
            thumbnail_margin += 40

    image = ImageTk.PhotoImage(im)

    global LabelImage
    LabelImage = ttk.Label(frameProgress, image=image)
    LabelImage.grid(sticky = W, row=1, column=0, pady = 5, padx = 7)

    global LabelSongname
    LabelSongname = ttk.Label(frameProgress, text = songname_str, anchor="w", justify = "left")
    LabelSongname.grid(sticky = W, row=0, column=0, pady = 10, padx = 7)

    global LabelInfo
    LabelInfo = ttk.Label(frameProgress, text = info_str, anchor="w", justify = "left")
    LabelInfo.grid(sticky = W, row=1, column=0, pady = 5, padx = thumbnail_margin)

    global LabelProgress
    LabelProgress = ttk.Label(frameProgress, text = " 0.0%", anchor="w", justify = "left")
    LabelProgress.grid(sticky = W, row=2, column=0, pady = 10, padx = 424)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.add_post_processor(MyCustomPP(), when='post_process')
            ydl.download([url])
        
    except yt_dlp.utils.DownloadError as error:
        print(error)
        DownloadErrorStatus = True
        while DownloadErrorStatus == True:
            print("There was a problem during the download, automatically restarting!")

            if file_format == "mp3":
                concatenated_bitrate = clicked.get()
                bitrate = concatenated_bitrate.split("Kbps")[0]
                format = 'bestaudio/best'
                ydl_opts = {'verbose': is_verbose,'no-part': True,'quiet': True,"external_downloader_args": ['-loglevel', 'panic'], 'format': format,'outtmpl': directory,'ffmpeg_location': ffmpeg_path, 'noplaylist': noplaylist,'progress_hooks': [my_hook], 'cookiefile' : 'cookies.txt', 'playliststart': (playlist_start + store()), 'playlistend': playlist_end,'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': bitrate},{'key': 'FFmpegMetadata', 'add_metadata': True}]}

            elif file_format == "mp4":
                concatenated_quality = clicked2.get()
                quality = concatenated_quality.split("p")[0]
                format = 'bestvideo[height<='+ quality +'][vbr<=12000][ext=mp4]+bestaudio[ext=m4a]/best[vbr<=12000][ext=mp4]/best'
                ydl_opts = {'verbose': is_verbose,'no-part': True,'quiet': True,"external_downloader_args": ['-loglevel', 'panic'], 'format': format,'outtmpl': directory,'ffmpeg_location': ffmpeg_path, 'noplaylist': noplaylist,'progress_hooks': [my_hook], 'cookiefile' : 'cookies.txt', 'playliststart': (playlist_start + store()), 'playlistend': playlist_end,'postprocessors':[{'key':'FFmpegVideoConvertor','preferedformat': 'mp4'}]}
            try:
                yt_dlp.YoutubeDL(ydl_opts).download([url])
                DownloadErrorStatus = False
            except yt_dlp.utils.DownloadError as error:
                print(error)
                DownloadErrorStatus = True

    for widgets in frameProgress.winfo_children():
        widgets.destroy()
    frameProgress.grid_forget()

    CurrentSong = 0
    store(CurrentSong)

    PreviousSong = -1
    store2(PreviousSong)

    SpawnButton2()
    adjust_window_size()  # Reset to base size
    notification.notify(title = 'Download Complete!', message = f"{NotificationText} has been downloaded.", app_icon = 'youtube-icon.ico', timeout = 10)

def start_convert():
    threading.Thread(target=convert).start()

def my_hook(d):
    # Safely get video index for playlists, default to 0 for single videos
    if 'info_dict' in d and 'playlist_autonumber' in d['info_dict']:
        video_index = d['info_dict']['playlist_autonumber'] - 1
    else:
        video_index = 0
    if d['status'] == 'downloading':
        My_progress['mode'] = 'determinate'
        progress_str = d['_percent_str'].replace("\x1b[0;94m ","").replace("\x1b[0m", "")
        if store() != store2():
            if store2() == -1: 
                PreviousSong = 0
                store2(PreviousSong)

            if noplaylist == True:
                # Safe access for single video
                title = video_infos.get('title', 'Unknown')
                uploader = video_infos.get('uploader', 'Unknown')
                duration = video_infos.get('duration', 0)
                songname_str = f"Downloading \"{title}\""
                info_str = f"Title : \"{title}\"\nChannel : \"{uploader}\"\nDuration : {str(datetime.timedelta(seconds=int(duration)))}"

            if noplaylist == False:
                # Safe access for playlist entries
                try:
                    if 'entries' in video_infos and video_index < len(video_infos['entries']):
                        entry = video_infos['entries'][video_index]
                        title = entry.get('title', 'Unknown')
                        uploader = entry.get('uploader', 'Unknown')
                        duration = entry.get('duration', 0)
                        thumbnail_url = entry.get('thumbnail', '')
                        playlist_title = video_infos.get('title', 'Unknown Playlist')
                        
                        songname_str = f"Downloading video {video_index+1} of {playlist_length+1} from the playlist \"{playlist_title}\""
                        info_str = f"Title : \"{title}\"\nChannel : \"{uploader}\"\nDuration : {str(datetime.timedelta(seconds=int(duration)))}"
                        
                        # Load thumbnail if available
                        if thumbnail_url:
                            try:
                                u = urllib.request.urlopen(thumbnail_url)
                                raw_data = u.read()
                                u.close()
                                im = Image.open(BytesIO(raw_data))
                                if " - Topic" in uploader:
                                    width, height = im.size
                                    left = int((width - height)/2)
                                    top = 0
                                    right = width - int((width - height)/2)
                                    bottom = height
                                    im = im.crop((left, top, right, bottom))
                                im.thumbnail((100, 60))
                                image = ImageTk.PhotoImage(im)
                                LabelImage.configure(image=image)
                                LabelImage.image=image
                            except Exception as e:
                                print(f"Could not load thumbnail: {e}")
                    else:
                        songname_str = "Processing playlist..."
                        info_str = "Loading video information..."
                except Exception as e:
                    print(f"Error accessing playlist data: {e}")
                    songname_str = "Processing playlist..."
                    info_str = "Loading video information..."
                
            LabelInfo.configure(text=info_str)
            LabelInfo.text=info_str
            LabelSongname.configure(text=songname_str)
            LabelSongname.text=songname_str

    PreviousSong = store()
    store2(PreviousSong)

    if d['status'] == 'finished':
        My_progress['mode'] = 'indeterminate'
        My_progress.start(50)
        progress_str = "Processing"
        
        # Safe access to video title
        if noplaylist == True:
            title = video_infos.get('title', 'Unknown') if video_infos else 'Unknown'
            songname_str = f"Finished downloading \"{title}\""
        else:
            # For playlists, try to get the current video title
            try:
                if video_infos and 'entries' in video_infos and video_index < len(video_infos['entries']):
                    title = video_infos['entries'][video_index].get('title', 'Unknown')
                else:
                    title = 'Unknown'
                songname_str = f"Finished downloading \"{title}\""
            except (KeyError, IndexError):
                songname_str = "Finished downloading video"
        
        if noplaylist == False:
            TotalProgressPercentage = ((video_index+1)/(playlist_length+1))*100
            Total_progress["value"] = int(TotalProgressPercentage)
    
            if int(TotalProgressPercentage) == 100:
                LabelPercentage = 'Done'
            else:
                LabelPercentage = f" {TotalProgressPercentage:.1f}%"
            LabelTotalProgress.configure(text=LabelPercentage)
            LabelTotalProgress.text=LabelPercentage

        CurrentSong = video_index + 1
        store(CurrentSong)

    LabelProgress.configure(text=progress_str)

    if d['status'] == 'downloading':   
        try:
            percentage = int(float(d['_percent_str'].replace("\x1b[0;94m ","").replace("\x1b[0m", "").replace('%','')))
        except:
            percentage = 0
        My_progress["value"] = percentage

def replaceMp3():
    w.destroy()
    global w2
    global clicked2
    clicked2 = StringVar()
    clicked2.set("720p")

    quality = ["144p", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
    w2 = ttk.OptionMenu(frame1, clicked2, quality[4], *quality)
    w2.grid(row=0, column=4)

def replaceMp4():
    w2.destroy()
    global w
    global clicked2
    clicked2 = StringVar()
    clicked2.set("192kps")

    bitrates = ["32Kbps", "96Kbps", "128Kbps", "192Kbps", "256Kbps", "320Kbps"]
    w = ttk.OptionMenu(frame1, clicked, bitrates[3], *bitrates)
    w.grid(row=0, column=4)

        
frame0 = LabelFrame(root, bg='#454746', border = 0)
frame0.grid(sticky = W, row=1, column=0)

frame1 = LabelFrame(root, bg='#454746', border = 0)
frame1.grid(sticky = W, row=2, column=0)

clicked = StringVar()
clicked.set("192Kbps")

bitrates = ["32Kbps", "96Kbps", "128Kbps", "192Kbps", "256Kbps", "320Kbps"]
w = ttk.OptionMenu(frame1, clicked, bitrates[3], *bitrates)
w.grid(row=0, column=4)

frame2 = LabelFrame(root, bg='#454746', border = 0)
frame2.grid(sticky = W, row=3, column=0)

frame3 = LabelFrame(root, bg='#454746', border = 0)
frame3.grid(sticky = W, row=6, column=0)

Label3 = ttk.Label(frame1, text = "  File output format :    ", anchor="w", justify = "left")
Label3.grid(sticky = W, row=0, column=0, pady = 10)

Label4 = ttk.Label(frame2, text = "  Playlist download :    ", anchor="w", justify = "left")
Label4.grid(sticky = W, row=0, column=0, pady = 10)

def addentry():
    global Label5
    Label5 = ttk.Label(frame2, text = "                  From video ")
    Label5.grid(row=0, column=4, padx = 2)
    global Entry3
    Entry3 = ttk.Entry(frame2,width=5)
    Entry3.insert(0, '...')
    Entry3.bind("<FocusIn>", lambda args: Entry3.delete('0', 'end'))
    Entry3.grid(row=0, column=5)
    global Label6
    Label6 = ttk.Label(frame2, text = " to ")
    Label6.grid(row=0, column=6)
    global Entry4
    Entry4 = ttk.Entry(frame2,width=5)
    Entry4.insert(0, '...')
    Entry4.bind("<FocusIn>", lambda args: Entry4.delete('0', 'end'))
    Entry4.grid(row=0, column=7)

def removeentry():
    Label5.destroy()
    Entry3.destroy()
    Label6.destroy()
    Entry4.destroy()

Entry1 = ttk.Entry(root,width=74)
Entry1.insert(0, 'Enter a youtube URL')
Entry1.bind("<FocusIn>", lambda args: Entry1.delete('0', 'end'))
Entry1.grid(sticky = W, row=0,column=0, pady=10, padx=5)

Entry2 = ttk.Entry(master=frame0,textvariable=folder_path, width=59)
Entry2.insert(0, 'Choose a path for your file')
Entry2.bind("<FocusIn>", lambda args: Entry2.delete('0', 'end'))
Entry2.grid(row=0, column=0, padx = 5, pady=5)


Button1 = ttk.Button(frame0, text="Browse", command=browse_button, cursor="hand2")
Button1.grid(row=0, column=1)

def SpawnButton2():
    global Button2
    Button2 = Button(root, text="Click here to launch download",font=("Bahnschrift",12), command=start_convert, border = 0, fg ="white", bg="#186a3b", pady=5, padx =10,activebackground="#589974",activeforeground="white", cursor="hand2")
    Button2.grid(sticky = W, row=4, column=0, pady = 2, padx = 110)
SpawnButton2()

radio_button_format= IntVar()
radio_button_format.set(1)

radio_button_playlist= IntVar()
radio_button_playlist.set(True)


Choice1 = ttk.Radiobutton(frame1, text="Mp3", command = replaceMp4, variable = radio_button_format, value = 1, cursor="hand2")
Choice1.grid(sticky = W, row=0, column=1)

Choice1 = ttk.Radiobutton(frame1, text="Mp4", command = replaceMp3, variable = radio_button_format, value = 2, cursor="hand2")
Choice1.grid(row=0, column=3)

Choice2 = ttk.Radiobutton(frame2, text="Yes", command = addentry, variable = radio_button_playlist, value = False, cursor="hand2")
Choice2.grid(sticky = W, row=0, column=3, padx = 5)

Choice2 = ttk.Radiobutton(frame2, text="No", command = removeentry, variable = radio_button_playlist, value = True, cursor="hand2")
Choice2.grid(row=0, column=1, padx = 3)




Label8 = ttk.Label(frame3, text = "It is not illegal to convert a Youtube video to MP3. But it is illegal to download a copyrighted\nmusic video. Using a Youtube converter to download a personal copy is against US copy-\nright law, so please use this software only to convert YouTube videos that are copyright free.", anchor="w",font=("Abadi Extra Light",8, "italic"), justify = LEFT)
Label8.grid(sticky = W, row=0, column=0, padx = 10 , pady = 8)

def adjust_window_size(base_width=None, base_height=None, extra_height=0):
    """
    Dynamically adjust window size based on content and platform
    """
    if base_width is None:
        base_width = PLATFORM_SCALE['width_base']
    if base_height is None:
        base_height = PLATFORM_SCALE['height_base']
    
    try:
        # Try advanced font-based scaling
        test_font = tkFont.Font(family=default_font[0], size=default_font[1])
        char_width = test_font.measure('M')
        char_height = test_font.metrics('linespace')
        
        # Base scaling factors (Windows reference)
        reference_char_width = 8
        reference_char_height = 13
        
        width_scale = max(char_width / reference_char_width, 0.8)  # Minimum scale
        height_scale = max(char_height / reference_char_height, 0.8)
        
        # Calculate new dimensions
        new_width = max(int(base_width * width_scale), base_width)
        new_height = max(int((base_height + extra_height) * height_scale), base_height + extra_height)
        
    except Exception:
        # Fallback to platform constants if font scaling fails
        new_width = base_width
        new_height = base_height + extra_height
    
    # Apply the new size
    root.geometry(f"{new_width}x{new_height}")
    return new_width, new_height

# Platform-specific size adjustments
PLATFORM_SCALE = {
    'width_base': 466,
    'height_base': 250,
    'height_extended': 385,
    'height_single': 350
}

# Adjust for Linux font differences
if os.name != 'nt':
    PLATFORM_SCALE['width_base'] = 500
    PLATFORM_SCALE['height_base'] = 270
    PLATFORM_SCALE['height_extended'] = 420
    PLATFORM_SCALE['height_single'] = 380

# Apply initial size adjustment after all widgets are created
root.update_idletasks()  # Ensure all widgets are rendered
adjust_window_size()

root.mainloop()