# Image Converter

A powerful image conversion tool that processes photos for e-ink displays with enhanced visual quality.

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

### Using Conda (Recommended)

1. Clone or download this repository
2. Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/download/)
3. Open your terminal/command prompt
4. Navigate to the project directory
5. Create the environment using the provided `environment.yml` file:

```bash
conda env create -f environment.yml
```

6. Activate the environment:

```bash
conda activate conv
```

### Manual Setup (Alternative)

If you don't want to use conda, install the required packages manually:

```bash
pip install pillow pillow-heif tqdm pyinstaller
```

## Usage

Run the script directly:

```bash
python convert.py
```

The script will guide you through the following options:
- Select orientation (portrait, landscape, or both)
- Choose conversion mode (scale or cut)
- Set enhancement levels (brightness, contrast, saturation)
- Configure date display options

Converted images will be saved in a `pic/` subfolder.

## Building Executable

To create a standalone executable that can run on any Windows PC (without Python):

```bash
# Activate the conda environment first
conda activate conv

# Build the executable
pyinstaller --onefile --name ImageConverter --noconfirm convert.py
```

The executable will be created in the `dist/` folder. You can share `ImageConverter.exe` with anyone - no Python installation required!

## Notes

- HEIC support requires the pillow-heif library, which is included in the conda environment
- For best results on e-ink displays, use the default enhancement settings
- The progress bar requires the tqdm library

## License

This project is open source and available under the MIT License. 