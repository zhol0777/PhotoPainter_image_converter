# encoding: utf-8

import argparse
import mimetypes
import sys
from pathlib import Path
from typing import Any, Union

from PIL import ExifTags, Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from pillow_heif import register_heif_opener  # type: ignore
from tqdm import tqdm

EXIF_DATE_FIELD_NAMES = ["DateTimeOriginal", "DateTimeDigitized", "DateTime", "XPDateTaken"]
HARDCODED_PICTURE_SUBFOLDER = "pic"
HARDCODED_MANIFEST_FILENAME = "fileList.txt"


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare images in working directory for display "
                                                 "on WaveShare PhotoPaper.")
    parser.add_argument("--orientation", choices=["portrait", "landscape", "both"],
                        default="both", help="(default: both)")
    parser.add_argument("-icv", "--image-conversion-mode", choices=["scale", "cut"], default="cut",
                        help="(default: cut)")
    parser.add_argument("--dithering-algorithm", default=Image.Dither.FLOYDSTEINBERG, type=int,
                        choices=[Image.Dither.NONE, Image.Dither.FLOYDSTEINBERG],
                        help="(default: Image.Dither.FLOYDSTEINBERG (3))")
    parser.add_argument("--brightness", type=float, default=1.2, help="(default: 1.2)")
    parser.add_argument("--contrast", type=float, default=1.4, help="(default: 1.4)")
    parser.add_argument("--saturation", type=float, default=1.3, help="(default: 1.3)")
    parser.add_argument("--show-date", action="store_true", default=False)
    parser.add_argument("--date-color", choices=["black", "blue", "green", "red"], default="blue")
    parser.add_argument("--date-size", type=int, default=10, help="(default: 10)")
    parser.add_argument("--delete-old-images", action="store_true", default=False)
    parser.add_argument("--disk-path", default=".",
                        help="Where to place output files (sd card is recommended)")
    parser.add_argument("--photos-path", default=".",
                        help="Directory where photos are located")
    return parser.parse_args()


def extract_exif_data(input_image: Image.Image) -> dict[str, Any]:
    """Assign human-readable keys to replace EXIF magic numbers """
    rebuilt_dict = {}
    if exif := input_image._getexif():  # type: ignore
        for key, val in exif.items():  # type: ignore
            if key in ExifTags.TAGS:
                rebuilt_dict[ExifTags.TAGS[key]] = val
    return rebuilt_dict


def extract_date_str(input_image: Image.Image) -> Union[str, None]:
    date_str = None
    if rebuilt_exif_data := extract_exif_data(input_image):
        for date_field in EXIF_DATE_FIELD_NAMES:
            if date_field in rebuilt_exif_data:
                raw_date = rebuilt_exif_data[date_field]
                date_str = raw_date[:10].replace(":", "-")
                break
    return date_str


def apply_date_to_image(input_image: Image.Image, modified_image: Image.Image,
                        args: argparse.Namespace) -> None:
    # If date was found, add it to the image BEFORE quantization
    if date_str := extract_date_str(input_image):
        # Create a drawing context
        draw = ImageDraw.Draw(modified_image)
        # Try to use a default font, fallback to default if not available
        try:
            # Use smaller font size as requested
            font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]
            try:
                font = ImageFont.truetype("arial.ttf", size=args.date_size)
            except Exception:
                font = ImageFont.truetype("DejaVuSans.ttf", size=args.date_size)
        except IOError:
            # If no TrueType fonts available, use default
            font = ImageFont.load_default(size=args.date_size)

        # Calculate position (bottom right with padding)
        text_width = draw.textlength(date_str, font=font)

        # Use different padding for horizontal and vertical to make box shorter
        h_padding = 8  # Horizontal padding (left/right)
        v_padding_top = 2  # Reduced top padding by 1px
        v_padding_bottom = 3  # Keep bottom padding unchanged

        # Calculate height with asymmetric padding
        rect_width = text_width + h_padding * 2
        rect_height = args.date_size + v_padding_top + v_padding_bottom

        # Position the rectangle in the bottom right corner
        # Move rect_y down by 1px to reduce the box from the top
        rect_x = modified_image.width - rect_width - 10
        rect_y = modified_image.height - rect_height - 10

        # Set background color based on user preference - define BEFORE using it
        bg_color = (0, 0, 128)  # Default to dark blue
        match args.date_color:
            case "black":
                bg_color = (0, 0, 0)
            case "blue":
                bg_color = (0, 0, 128)
            case "green":
                bg_color = (0, 80, 0)
            case "red":
                bg_color = (128, 0, 0)

        # Create rounded rectangle for background
        # Use smaller corner radius for smaller height
        corner_radius = min(
            6, int(rect_height // 2.5)
        )  # Adjusted ratio, max 6px

        # Create a transparent image and draw a rounded rectangle
        rounded_rect = Image.new(
            "RGBA", (int(rect_width), int(rect_height)), (0, 0, 0, 0)
        )
        rect_draw = ImageDraw.Draw(rounded_rect)

        # Draw the rectangle with rounded corners
        rect_draw.rounded_rectangle(
            ((0, 0), (rect_width - 1, rect_height - 1)),
            fill=bg_color + (200,),  # Add alpha for semi-transparency
            radius=corner_radius,
        )

        # Paste the rectangle onto the main image
        modified_image.paste(
            rounded_rect, (int(rect_x), int(rect_y)), rounded_rect
        )

        # Calculate text position to center it in the box
        text_x = rect_x + h_padding
        # Keep text at the same position as before, equivalent to the old centering formula
        text_y = rect_y + (rect_height - args.date_size) // 2 - 1

        # Draw text in white
        draw.text(
            (text_x, text_y), date_str, fill=(255, 255, 255), font=font
        )


def filter_images_based_on_orientation(image_files: list[Path], orientation: str) -> list[Path]:
    filtered_files = []
    skipped_file_count = 0

    print(f"\nFiltering images for {orientation} orientation...")

    # Don"t use progress bar for filtering, just process files silently
    for filename in image_files:
        try:
            img = Image.open(filename)
            width, height = img.size

            # Default to dimension-based orientation
            is_landscape = width > height
            exif_orientation = None

            # Try to check EXIF data for more accurate orientation
            try:
                if exif_orientation := extract_exif_data(img).get("Orientation"):
                    # Orientations 5-8 indicate the image should be rotated to portrait
                    if exif_orientation in [5, 6, 7, 8]:
                        is_landscape = False
                    # Orientations 1-4 maintain landscape/portrait based on dimensions
            except (AttributeError, KeyError, TypeError):
                # If EXIF check fails, stick with dimension-based orientation
                pass
            img.close()

            # Add to the appropriate list
            if (orientation == "landscape" and is_landscape) or (
                orientation == "portrait" and not is_landscape
            ):
                filtered_files.append(filename)
            else:
                skipped_file_count += 1

        except Exception as e:
            print(f"Error checking orientation of {filename}: {e}")

    if filtered_files:
        print(
            f"\nKept {len(filtered_files)} {orientation} images, "
            f"skipped {skipped_file_count} images"
        )
    else:
        print(f"No {orientation} images found")
        sys.exit(1)
    return filtered_files


def correct_rotation(input_image: Image.Image) -> Image.Image:
    # Apply EXIF rotation correction
    transpositions: list[Image.Transpose] = []
    match extract_exif_data(input_image).get("Orientation"):
        case 2:
            transpositions = [Image.Transpose.FLIP_LEFT_RIGHT]
        case 3:
            transpositions = [Image.Transpose.ROTATE_180]
        case 4:
            transpositions = [Image.Transpose.FLIP_TOP_BOTTOM]
        case 5:
            transpositions = [Image.Transpose.FLIP_LEFT_RIGHT,
                              Image.Transpose.ROTATE_90]
        case 6:
            transpositions = [Image.Transpose.ROTATE_270]
        case 7:
            transpositions = [Image.Transpose.FLIP_LEFT_RIGHT,
                              Image.Transpose.ROTATE_270]
        case 8:
            transpositions = [Image.Transpose.ROTATE_90]
    for transposition in transpositions:
        input_image = input_image.transpose(transposition)
    return input_image


def scale_input_image(input_image: Image.Image, width: int, target_width: int,
                      height: int, target_height: int) -> Image.Image:
    # Computed scaling
    scale_ratio = max(target_width / width, target_height / height)

    # Calculate the size after scaling
    resized_width = int(width * scale_ratio)
    resized_height = int(height * scale_ratio)

    # Resize image
    output_image = input_image.resize((resized_width, resized_height))

    # Create the target image and center the resized image
    modified_image = Image.new(
        "RGB", (target_width, target_height), (255, 255, 255)
    )
    left = (target_width - resized_width) // 2
    top = (target_height - resized_height) // 2
    modified_image.paste(output_image, (left, top))
    return modified_image


def main():
    mimetypes.init()
    register_heif_opener()
    args = parse_args()

    # Create pic/ subfolder if it doesn"t exist
    output_dir = Path(args.disk_path) / HARDCODED_PICTURE_SUBFOLDER
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    elif args.delete_old_images:
        # remove all files in this directory
        for filename in output_dir.iterdir():
            try:
                filename.unlink()  # need to see if this breaks anything
            except Exception as e:
                print("Failed to delete %s. Reason: %s" % (filename, e))

    # Get all image files in current directory
    image_files = []
    for entry in Path(args.photos_path).iterdir():
        if entry.is_file():
            if guessed_type := mimetypes.guess_type(entry.name)[0]:
                if "image" in guessed_type:
                    image_files.append(entry)

    if not image_files:
        print("No image files found in the current directory")
        sys.exit(1)

    # Filter images by orientation if needed
    if args.orientation != "both":
        image_files = filter_images_based_on_orientation(image_files, args.orientation)

    # Process each image
    converted_files = []
    counter = 1

    # Create a progress bar to show conversion progress
    pbar = tqdm(total=len(image_files), desc="Converting images", unit=" image")

    for input_filename in image_files:
        try:
            # Read input image
            input_image = Image.open(input_filename)

            input_image = correct_rotation(input_image)

            # Get the original image size
            width, height = input_image.size

            # Specified target size
            # Set dimensions based on the actual image orientation
            if width > height:
                # This is a landscape image
                target_width, target_height = 800, 480
            else:
                # This is a portrait image
                target_width, target_height = 480, 800

            if args.image_conversion_mode == "scale":
                modified_image = scale_input_image(input_image, width, target_width,
                                                   height, target_height)
            elif args.image_conversion_mode == "cut":
                box = (0, 0, width, height)

                modified_image = ImageOps.pad(
                    input_image.crop(box),
                    size=(target_width, target_height),
                    color=(255, 255, 255),
                    centering=(0.5, 0.5),
                )
            else:
                raise ValueError(f"Unknown image conversion mode: {args.image_conversion_mode}")
            input_image.close()

            # Apply enhancements (brightness, contrast and saturation)
            modified_image = ImageEnhance.Brightness(modified_image).enhance(args.brightness)
            modified_image = ImageEnhance.Contrast(modified_image).enhance(args.contrast)
            modified_image = ImageEnhance.Color(modified_image).enhance(args.saturation)

            # Add edge enhancement
            modified_image = modified_image.filter(ImageFilter.EDGE_ENHANCE)

            # Add noise reduction
            modified_image = modified_image.filter(ImageFilter.SMOOTH)

            # Add sharpening for better detail visibility
            modified_image = modified_image.filter(ImageFilter.SHARPEN)

            if args.show_date:
                apply_date_to_image(input_image, modified_image, args)

            # Create a palette object with exact display colors
            # (Black, White, Green, Blue, Red, Yellow)
            pal_image = Image.new("P", (1, 1))
            pal_image.putpalette(
                (
                    0, 0, 0,        # Black
                    255, 255, 255,  # White
                    0, 255, 0,      # Green
                    0, 0, 255,      # Blue
                    255, 0, 0,      # Red
                    255, 255, 0,    # Yellow
                ) 
                + (0, 0, 0) * 246
            )

            # Perform quantization on the enhanced image (including the date text)
            quantized_image = modified_image.quantize(
                dither=args.dithering_algorithm,
                palette=pal_image).convert("RGB")
            modified_image.close()

            # Save output image to pic/ subfolder with sequentially numbered filename
            sequential_name = f"{counter:06d}.bmp"  # Format as 000001.bmp
            output_filename = output_dir / sequential_name
            quantized_image.save(output_filename)

            # Add to list of converted files
            converted_files.append(output_filename)

            # Update progress instead of printing
            pbar.update(1)
            pbar.set_postfix(file=Path(input_filename).name, status="Success")

            # Increment counter for next file
            counter += 1
        except Exception as e:
            # Show errors even with progress bar, but use pbar.write for cleaner output
            pbar.update(1)
            pbar.set_postfix(file=Path(input_filename).name, status="Error")
            pbar.write(f"Error processing {input_filename}: {e}")
            raise

    # Close the progress bar
    pbar.close()

    # Write the list of converted files to fileList.txt
    if converted_files:
        manifest_path = Path(args.disk_path) / HARDCODED_MANIFEST_FILENAME
        with manifest_path.open("w", encoding="utf-8") as f:
            for file in converted_files:
                f.write(f"{file}\n")
        pbar.write(f"Created {HARDCODED_MANIFEST_FILENAME} with {len(converted_files)} entries")


if __name__ == "__main__":
    main()