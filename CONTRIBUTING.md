# Contributing

Thank you for your interest in contributing to yt-dlp Convenient GUI!

## Adding a new translation

The app uses simple JSON files for translations. No coding experience is required to add a new language.

### Steps

1. **Copy the reference file**

   Copy `locales/en.json` to `locales/<code>.json`, where `<code>` is the [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) language code (e.g. `de` for German, `es` for Spanish, `pt` for Portuguese).

2. **Update the `_meta` block**

   ```json
   "_meta": {
       "language": "Deutsch",
       "code": "de",
       "authors": ["your-github-username"],
       "version": "1.0.0"
   }
   ```

3. **Translate the values**

   Each line has a key (do **not** change it) and a value (translate it):

   ```json
   "button.download": "Click here to launch download",
   ```
   becomes:
   ```json
   "button.download": "Klicken Sie hier, um den Download zu starten",
   ```

   **Important:** keep all `{placeholders}` exactly as they are — only translate the text around them:

   ```json
   "download.playlist_element": "Downloading element {index} out of {total} from the playlist {playlist_title}",
   ```

4. **Register the language**

   Open `src/utils/i18n_utils.py` and add your language to the `AVAILABLE_LANGUAGES` dictionary:

   ```python
   AVAILABLE_LANGUAGES = {
       "en": "English",
       "fr": "Français",
       "de": "Deutsch",       # ← add your language here
   }
   ```

   Use the native name of the language as the value (e.g. "Español", not "Spanish").

5. **Submit a pull request**

   Your PR should contain exactly two changes:
   - The new `locales/<code>.json` file
   - The one-line addition in `src/utils/i18n_utils.py`

### Guidelines

- Use `locales/en.json` as the reference — it always contains all keys.
- Do not add or remove keys.
- Do not change key names.
- Keep the same JSON structure and formatting.
- Preserve leading/trailing spaces in values where present (e.g. `" to "`).
- If a string doesn't need translation (e.g. brand names like "MusicBrainz"), keep it as-is.
