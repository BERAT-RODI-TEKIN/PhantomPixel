"""English texts (the reference language: every key must exist here)."""

S = {
    # --- app ---------------------------------------------------------------
    "app.tagline": "Hide data inside images. Invisible to the eye.",

    # --- shared words ------------------------------------------------------
    "common.password": "Password",
    "common.with_password": "password-protected",
    "common.no_password": "no password",
    "common.folder": "open folder",
    "common.card_done": "Card: {path}",
    "common.saved": "Saved: {path}",
    "common.skipped": "skipped",

    # --- errors (engine, crypto, workflows, analyzer) ---------------------
    "err.cannot_open": "Could not open the image: {error}",
    "err.too_small": "The image is too small to contain data.",
    "err.no_data": "No PhantomPixel data found in this image.",
    "err.newer": "This image was made with a newer version of PhantomPixel (format {magic}). "
                 "Please update the program to open it.",
    "err.header_damaged": "The header is damaged: the image was probably modified after hiding.",
    "err.unknown_flags": "The header contains unknown options: the image is damaged.",
    "err.pw_required": "This data is protected by a password.",
    "err.wrong_pw": "Wrong password, or the image was modified after hiding "
                    "(JPEG conversion, resizing, screenshot, editing).",
    "err.corrupted": "The hidden data is damaged: the image was modified after hiding "
                     "(JPEG conversion, resizing, screenshot, editing). Use the original PNG file.",
    "err.payload_damaged": "The hidden data is damaged.",
    "err.decompress": "The hidden data could not be decompressed: it is damaged.",
    "err.decompress_big": "The hidden data expands to more than the allowed size ({limit}).",
    "err.gcm": "Wrong password, or the data was modified.",
    "err.overwrite_cover": "The output file would overwrite the cover image. Choose a different name.",
    "err.capacity": "The secret does not fit: it needs {need} bytes but this image holds about {cap}. "
                    "Use a larger image or a smaller secret.",
    "err.payload_too_large": "The secret is too large (limit {limit}).",
    "err.selfcheck_fail": "Self-check failed ({error}). Nothing was saved.",
    "err.selfcheck_mismatch": "Self-check failed: the data read back did not match. Nothing was saved.",
    "err.need_one": "Provide either a text message or a file to hide (exactly one).",
    "err.file_not_found": "File not found: {path}",
    "err.diff_sizes": "The two images have different sizes and cannot be compared.",

    # --- statistical detector ---------------------------------------------
    "detect.high": "High suspicion: value pairs are unusually balanced",
    "detect.medium": "Medium suspicion",
    "detect.low": "Low suspicion: no obvious LSB trace",
    "detect.unknown": "Not enough data to analyse",

    # --- interactive UI: generic -------------------------------------------
    "ui.tip_back": "Tip: type [bold]<[/bold] at any prompt to go back one step.",
    "ui.error_title": "Error",
    "ui.file_hint_keep": "(Enter = keep {name}, ? = browse, or drop a file here)",
    "ui.file_hint_skip": "(Enter = skip, ? = browse, or drop a file here)",
    "ui.file_hint": "(drop a file here, paste a path, or press Enter to browse)",
    "ui.no_dialog": "No file dialog available here: drop a file onto this window or paste its path.",
    "ui.no_file": "No file selected.",
    "ui.file_not_found": "File not found: {path}",
    "ui.enter_back": "back to menu",
    "ui.press_key": "Press one of the keys above, or Enter.",
    "ui.cancelled": "Cancelled.",
    "ui.unexpected": "Unexpected error: {error}",
    "ui.bye": "Bye.",
    "ui.prompt": "phantom ›",

    # --- hide wizard --------------------------------------------------------
    "hide.cover": "Cover image",
    "hide.cover_ok": "{w}×{h} px · up to {cap} ({cap_pw} with a password) · compressible data fits more",
    "hide.secret": "Secret",
    "hide.secret_hint": "(type a message, or press Enter to choose a file)",
    "hide.pick_title": "Choose the file to hide",
    "hide.file_label": "File to hide",
    "hide.what_message": "message, {n} bytes",
    "hide.what_file": "file {name} ({size})",
    "hide.too_big": "Too big: {size}, but this image holds about {cap}, even after compression. "
                    "Type < to pick a larger image, or choose a smaller secret.",
    "hide.usage_ok": "({pct}% of this image)",
    "hide.pw_hint": "(optional, Enter = no password; there is no recovery if you forget it)",
    "hide.pw_repeat": "Repeat password",
    "hide.pw_mismatch": "The passwords do not match, try again.",
    "hide.pw_too_big": "With a password this secret needs {size}, but the image holds about {cap}. "
                       "Choose a smaller secret.",
    "hide.ready": "Ready",
    "hide.row_cover": "Cover",
    "hide.row_secret": "Secret",
    "hide.row_protection": "Protection",
    "hide.row_usage": "Image usage",
    "hide.prot_on": "AES-256-GCM + password-keyed scattering",
    "hide.prot_off": "none (anyone with this tool can read it)",
    "hide.confirm": "Hide it now?",
    "hide.confirm_hint": "(Enter = yes, < = go back)",
    "hide.running": "Hiding and verifying...",
    "hide.done": "Done",
    "hide.row_saved": "Saved as",
    "hide.row_hidden": "Hidden",
    "hide.row_verified": "Verified",
    "hide.row_note": "Note",
    "hide.hidden_compressed": "{size} (compressed from {orig})",
    "hide.verified_yes": "✓ read back from the file and compared",
    "hide.note_png": "Share this file as a PNG file. JPEG / social media recompression destroys the data.",
    "hide.act_card": "make share card",

    # --- extract wizard -----------------------------------------------------
    "x.image": "Image with hidden data",
    "x.no_data": "No PhantomPixel data found in this image.",
    "x.jpeg": " This is a JPEG: its compression destroys hidden data. You need the original PNG file.",
    "x.found": "Hidden data found: {size}, {kind}",
    "x.running": "Extracting...",
    "x.msg_title": "Hidden message",
    "x.act_save": "save as .txt",
    "x.file_title": "File extracted",
    "x.file_saved": "Saved as {path}",

    # --- inspect wizard -----------------------------------------------------
    "i.image": "Image to inspect",
    "i.original": "Original image (optional, adds a comparison)",
    "i.running": "Analysing...",
    "i.found": "[bold green]✔ FOUND[/]  {size}, {kind}, format v{version}",
    "i.none": "[bold yellow]✘ none found[/]",
    "i.row_sig": "PhantomPixel signature",
    "i.row_stat": "Statistical test",
    "i.row_psnr": "PSNR vs original",
    "i.row_changed": "Changed pixels",
    "i.title": "Inspection",
    "i.note": "The signature check is exact but only recognises images made by PhantomPixel. "
              "The statistical test is a heuristic: a low score does not prove an image is clean.",
    "i.act_extract": "extract it now",
    "i.act_lsb": "save LSB plane",
    "i.lsb_done": "LSB plane: {path}",

    # --- card wizard --------------------------------------------------------
    "c.original": "Original image (without hidden data)",
    "c.running": "Building card...",

    # --- capacity wizard ----------------------------------------------------
    "cap.image": "Image",
    "cap.title": "Capacity",
    "cap.row_size": "Size",
    "cap.row_cap": "Capacity",
    "cap.row_cap_pw": "With password",
    "cap.row_tip": "Tip",
    "cap.size_value": "{w} × {h} pixels",
    "cap.tip": "Figures are for incompressible data. Text and documents compress, so they often fit more. "
               "The less you fill, the less trace you leave.",

    # --- demo ---------------------------------------------------------------
    "demo.starting": "Starting demo...",
    "demo.step_cover": "Generating a cover image",
    "demo.step_hide": "Hiding the message inside the pixels",
    "demo.step_extract": "Extracting it again to verify",
    "demo.step_card": "Building the comparison card",
    "demo.recovered": "Text extracted from the image",
    "demo.row_check": "Check",
    "demo.row_protection": "Protection",
    "demo.row_quality": "Image quality",
    "demo.row_changed": "Changed pixels",
    "demo.row_files": "Files",
    "demo.check_ok": "[green]hidden and extracted text are identical[/]",
    "demo.check_bad": "[red]MISMATCH![/]",
    "demo.prot": "AES-256-GCM · password: [bold]{pw}[/]",
    "demo.prot_none": "none",
    "demo.quality": "PSNR {psnr} dB (above 40 dB is invisible to the eye)",
    "demo.changed": "{pct}% · largest colour change: {max}/255",
    "demo.title": "Demo result",
    "demo.opening": "Opening the comparison card...",
    "demo.act_inspect": "inspect the hidden image",
    "demo.message": (
        "SECRET DOCUMENT\n"
        "---------------\n"
        "This text was hidden inside the pixels of an image.\n"
        "Only the lowest bit of each red, green and blue value was changed:\n"
        "a colour moves by at most 1/255, which the human eye cannot notice.\n\n"
        "Without the password the text cannot be read (AES-256-GCM), and the hidden\n"
        "bits are scattered across the whole image, so there is no pattern to find.\n\n"
        "- PhantomPixel"
    ),

    # --- menu / smart mode / language --------------------------------------
    "menu.1": "Quick demo",
    "menu.1.d": "One key: hide, extract and show the comparison card",
    "menu.2": "Hide",
    "menu.2.d": "Hide a message or any file inside an image",
    "menu.3": "Extract",
    "menu.3.d": "Read hidden data back out of an image",
    "menu.4": "Inspect",
    "menu.4.d": "Detect hidden data, compare images, view the LSB plane",
    "menu.5": "Share card",
    "menu.5.d": "Original | hidden | difference map, ready to post",
    "menu.6": "Capacity",
    "menu.6.d": "How much data fits into an image?",
    "menu.7": "Language",
    "menu.7.d": "English · Türkçe · Русский",
    "menu.0": "Exit",
    "smart.found": "{name} contains hidden data. Let's extract it.",
    "smart.hide": "Let's hide something in {name}.",
    "lang.title": "Language",
    "lang.prompt": "Choose a language (Enter = keep current)",
    "lang.changed": "Language: {name}",

    # --- share card image (visuals.py) -------------------------------------
    "card.question": "Which one hides a secret?",
    "card.original": "ORIGINAL",
    "card.hidden": "HIDDEN DATA INSIDE",
    "card.diff": "DIFFERENCE MAP",
    "card.k_psnr": "PSNR",
    "card.k_changed": "CHANGED PIXELS",
    "card.k_hidden": "HIDDEN DATA",
    "card.k_protection": "PROTECTION",
    "card.none": "None",
    "card.footer": "LSB steganography  •  The lowest bit of every colour channel carries data",

    # --- file dialog --------------------------------------------------------
    "picker.images": "Images",
    "picker.all": "All files",
    "picker.title": "Choose a file",

    # --- command line (main.py) --------------------------------------------
    "cli.description": "Hide data inside images.",
    "cli.epilog": "Tip: pass just an image path (or drag an image onto the program) for smart mode.",
    "cli.h_lang": "interface language: en, tr or ru (remembered when chosen from the menu)",
    "cli.h_noanim": "skip the start-up animation",
    "cli.h_demo": "one-key demo",
    "cli.h_hide": "hide a message or file inside an image",
    "cli.h_cover": "cover image (any format; the result is always PNG)",
    "cli.h_message": "text to hide",
    "cli.h_file": "file to hide",
    "cli.h_pw_hide": "ask for a password (hidden input)",
    "cli.h_output": "output path (default: next to the cover, *_phantom.png)",
    "cli.h_card": "also create a share card",
    "cli.h_noverify": "skip the read-back self-check",
    "cli.h_extract": "extract hidden data",
    "cli.h_stego": "image that contains hidden data",
    "cli.h_pw_extract": "ask for the password (hidden input)",
    "cli.h_inspect": "inspect an image",
    "cli.h_original": "original image, for a comparison",
    "cli.h_card_cmd": "create a share card",
    "cli.h_capacity": "how much data fits into an image",
    "cli.h_capacity_image": "image to measure",
    "cli.h_json": "print the result as JSON (for scripts)",
    "cli.pw_prompt": "Password: ",
    "cli.written": "Written: {path}  (image usage {pct}%{verified})",
    "cli.verified": ", verified",
    "cli.file_saved": "File saved: {path}",
    "cli.signature": "Signature: {sig}",
    "cli.sig_found": "{size}, {kind}, format v{version}",
    "cli.sig_none": "none found",
    "cli.suspicion": "Statistical suspicion: {pct}% - {verdict}",
    "cli.psnr": "PSNR: {psnr} dB, changed pixels: {pct}%",
    "cli.cap_size": "Size: {w} × {h} pixels",
    "cli.cap_plain": "Capacity (incompressible data): {cap}",
    "cli.cap_pw": "Capacity with a password: {cap}",
    "cli.error": "Error: {error}",
    "cli.unexpected": "Unexpected error: {error}",
    "cli.press_enter": "Press Enter to close...",
    "cli.missing": "Missing libraries: {libs}",
    "cli.python_in_use": "Python in use: {path}",
    "cli.install_ask": "Install them now? (internet required) [Y/n]: ",
    "cli.install_failed": "Installation failed. Check your internet connection and try again.",
    "cli.install_manual": "To install them yourself, run:",
    "cli.install_venv": "On Linux, pip may refuse to install system-wide (externally managed environment). "
                        "In that case create a virtual environment first:  python3 -m venv .venv && "
                        ". .venv/bin/activate && pip install -r requirements.txt",
}
