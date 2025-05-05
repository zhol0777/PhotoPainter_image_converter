# Image Converter

```
usage: convert.py [-h] [--orientation {portrait,landscape,both}] [-icv {scale,cut}] [--dithering-algorithm {0,3}] [--brightness BRIGHTNESS]
                  [--contrast CONTRAST] [--saturation SATURATION] [--show-date] [--date-color {black,blue,green,red}]
                  [--date-size DATE_SIZE] [--delete-old-images]

Prepare images in working directory for display on WaveShare PhotoPaper.

options:
  -h, --help            show this help message and exit
  --orientation {portrait,landscape,both}
                        (default: both)
  -icv, --image-conversion-mode {scale,cut}
                        (default: cut)
  --dithering-algorithm {0,3}
                        (default: Image.Dither.FLOYDSTEINBERG (3))
  --brightness BRIGHTNESS
                        (default: 1.2)
  --contrast CONTRAST   (default: 1.4)
  --saturation SATURATION
                        (default: 1.3)
  --show-date
  --date-color {black,blue,green,red}
  --date-size DATE_SIZE
                        (default: 10)
  --delete-old-images
```

A image conversion tool that processes photos for e-ink displays with enhanced visual quality specifically for the Photo Painter (B) e-paper frame.

## Links
- Photo Painter (B) product information: https://www.waveshare.com/wiki/PhotoPainter_%28B%29
- Enhanced firmware repository: https://github.com/myevit/PhotoPainter_B/blob/master/README.md

## Features

- Convert images to optimized formats for e-ink displays
- Filter images by orientation (portrait/landscape)
- Apply image enhancements:
  - Brightness adjustment
  - Contrast enhancement
  - Color saturation
- Optional date display on images
- Handles multiple image formats including HEIC
- Batch processing with progress bar

## Setup

### Manual Setup (preferably with a venv)

```bash
pip install pillow pillow-heif tqdm
```

## Usage

Run the script directly:

```bash
python convert.py
```

Converted images will be saved in a `pic/` subfolder.

## Notes

- HEIC support requires the pillow-heif library
- For best results on e-ink displays, use the default enhancement settings

## License

This project is open source and available under the MIT License. 
