# Changelog

## 2.1.0

**Format `PPX3`.** New versions open images made by older versions, never the other way round:
v2.1 opens v2.0 images; v2.0 cannot open v2.1 images (it reports "no data"). The next format (`PPX4`, v2.2) will follow
the same rule, and v2.1 already recognises it and asks the user to update.

### Added
- **Start-up animation:** noise pixels resolve into the banner, then the tagline is typed out.
  Skipped with `--no-anim` or `PHANTOMPIXEL_NO_ANIM=1`, and automatically when the output is not a terminal or the window is small.
- **Languages:** English, Türkçe and Русский. Menu key `7`, or `--lang en|tr|ru`; the choice is remembered in
  `~/PhantomPixel/settings.json`. Order of precedence: `--lang`, `PHANTOMPIXEL_LANG`, saved choice, system language, English.
  The share card and `--help` are translated too.
- **Compression:** secrets are zlib-compressed before encryption when that makes them smaller. The wizard and
  `capacity` explain that the shown capacity is for incompressible data.
- **`capacity` command** (`python main.py capacity image.png`).
- **`--json`** for `hide`, `extract`, `inspect` and `capacity`: one JSON object on stdout, stable `code` on errors, exit status 1.
  `PHANTOMPIXEL_PASSWORD` supplies the password for `-p` in scripts.
- **Newer-version detection:** an image made by a newer PhantomPixel is refused with a clear message instead of "no data".
- **Release tooling:** GitHub Actions for tests (Linux + Windows) and for the Windows `.exe` with a SHA-256 checksum;
  `build_exe.bat` writes the checksum too.
- **Tests:** compatibility tests with the real v2.0 code and stored v2.0 images, edge cases (RGBA, palette, 16-bit, EXIF,
  tiny images), language completeness, CLI and animation. 87 tests in total (v2.0 had 19).

### Changed
- AES-256-GCM now authenticates the header (magic, flags, salt, length) as associated data.
- scrypt cost raised from 2^14 to 2^15 for new images (v2.0 images keep their own cost, so they still open).
- Statistical detector results carry a stable `level` (`low` / `medium` / `high`); the text follows the language.
- Image usage is now measured against the real space in the image, after compression.

### Fixed
- Transparent pixels of palette (`P`) and tRNS images were silently turned opaque.
- 16-bit greyscale images were clipped to white instead of being scaled to 8 bit.
- `pip` failures on Linux (externally managed environments) now explain the virtual-environment fix.
- The menu's "Capacity" entry now also exists as a command (`capacity`).

### Safety
- Decompression is capped at 512 MB so a tiny crafted image cannot expand into gigabytes.

## 2.0.0

Format `PPX2`: AES-256-GCM + scrypt, keyed Feistel permutation, CRC-32, read-back verification,
inspector, share card and the interactive menu.
