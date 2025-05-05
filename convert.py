# encoding: utf-8

from typing import Any, Union
import argparse
import mimetypes
import os
import sys

from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageDraw, ImageFont, ExifTags
from tqdm import tqdm
import pillow_heif  # type: ignore


EXIF_DATE_FIELD_NAMES = ["DateTimeOriginal", "DateTimeDigitized", "DateTime", "XPDateTaken"]
PICTURE_SUBFOLDER = "pic"


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare images in working directory for display "
                                                 "on WaveShare PhotoPaper.")
    parser.add_argument('--orientation', choices=['portrait', 'landscape', 'both'],
                        default='both', help='(default: both)')
    parser.add_argument('-icv', '--image-conversion-mode', choices=['scale', 'cut'], default='cut',
                        help='(default: cut)')
    parser.add_argument('--dithering-algorithm', default=Image.Dither.FLOYDSTEINBERG, type=int,
                        choices=[Image.Dither.NONE, Image.Dither.FLOYDSTEINBERG],
                        help='(default: Image.Dither.FLOYDSTEINBERG (3))')
    parser.add_argument('--brightness', type=float, default=1.2, help='(default: 1.2)')
    parser.add_argument('--contrast', type=float, default=1.4, help='(default: 1.4)')
    parser.add_argument('--saturation', type=float, default=1.3, help='(default: 1.3)')
    parser.add_argument('--show-date', action='store_true', default=False)
    parser.add_argument('--date-color', choices=['black', 'blue', 'green', 'red'], default='blue')
    parser.add_argument('--date-size', type=int, default=10, help='(default: 10)')
    parser.add_argument('--delete-old-images', action='store_true', default=False)
    parser.add_argument('--disk-path', default='.',
                        help='Where to place output files (sd card is recommended)')
    parser.add_argument('--photos-path', default='.',
                        help='Directory where photos are located')
    return parser.parse_args()


def extract_exif_data(input_image: Image.Image) -> dict[str, Any]:
    '''Assign human-readable keys to replace EXIF magic numbers '''
    rebuilt_dict = {}
    for key, val in input_image._getexif().items():  # type: ignore
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


def apply_date_to_image(input_image: Image.Image, enhanced_image: Image.Image,
                        args: argparse.Namespace,) -> None:
    # If date was found, add it to the image BEFORE quantization
    if date_str := extract_date_str(input_image):
        # Create a drawing context
        draw = ImageDraw.Draw(enhanced_image)
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
        rect_x = enhanced_image.width - rect_width - 10
        rect_y = enhanced_image.height - rect_height - 10

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
        enhanced_image.paste(
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


def main():
    mimetypes.init()
    pillow_heif.register_heif_opener()
    args = parse_args()

    # Create pic/ subfolder if it doesn't exist
    output_dir = os.path.join(args.disk_path, PICTURE_SUBFOLDER)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        if args.delete_old_images:
            # remove all files in this directory
            for filename in os.listdir(output_dir):
                try:
                    os.unlink(os.path.join(output_dir, filename))
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (filename, e))

    # Get all image files in current directory
    image_files = []
    for entry in os.scandir(args.photos_path):
        if entry.is_file():
            if guessed_type := mimetypes.guess_type(entry.name)[0]:
                if 'image' in guessed_type:
                    image_files.append(entry.path)

    if not image_files:
        print("No image files found in the current directory")
        sys.exit(1)

    # Filter images by orientation if needed
    if args.orientation != "both":
        filtered_files = []
        skipped_files = []

        print(f"\nFiltering images for {args.orientation} orientation...")

        # Don't use progress bar for filtering, just process files silently
        for filename in image_files:
            try:
                img = Image.open(filename)
                width, height = img.size

                # Default to dimension-based orientation
                is_landscape = width > height
                exif_orientation = None

                # Try to check EXIF data for more accurate orientation
                try:
                    if exif_orientation := extract_exif_data(img).get('Orientation'):
                        # Orientations 5-8 indicate the image should be rotated to portrait
                        if exif_orientation in [5, 6, 7, 8]:
                            is_landscape = False
                        # Orientations 1-4 maintain landscape/portrait based on dimensions
                except (AttributeError, KeyError, TypeError):
                    # If EXIF check fails, stick with dimension-based orientation
                    pass
                img.close()

                # Add to the appropriate list
                if (args.orientation == "landscape" and is_landscape) or (
                    args.orientation == "portrait" and not is_landscape
                ):
                    filtered_files.append(filename)
                else:
                    skipped_files.append(filename)

            except Exception as e:
                print(f"Error checking orientation of {filename}: {e}")

        # Update image_files to only include the filtered ones
        image_files = filtered_files

        print(
            f"\nKept {len(filtered_files)} {args.orientation} images, skipped {len(skipped_files)} images"
        )

        if not image_files:
            print(f"No {args.orientation} images found")
            sys.exit(1)

    # Process each image
    converted_files = []
    counter = 1

    # Create a progress bar to show conversion progress
    pbar = tqdm(total=len(image_files), desc="Converting images", unit=" image")

    for input_filename in image_files:
        try:
            # Read input image
            input_image = Image.open(input_filename)

            # Apply EXIF rotation correction
            match extract_exif_data(input_image).get('Orientation'):
                case 2:
                    input_image = input_image.transpose(Image.FLIP_LEFT_RIGHT)
                case 3:
                    input_image = input_image.transpose(Image.ROTATE_180)
                case 4:
                    input_image = input_image.transpose(Image.FLIP_TOP_BOTTOM)
                case 5:
                    input_image = input_image.transpose(
                        Image.FLIP_LEFT_RIGHT
                    ).transpose(Image.ROTATE_90)
                case 6:
                    input_image = input_image.transpose(Image.ROTATE_270)
                case 7:
                    input_image = input_image.transpose(
                        Image.FLIP_LEFT_RIGHT
                    ).transpose(Image.ROTATE_270)
                case 8:
                    input_image = input_image.transpose(Image.ROTATE_90)

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
                # Computed scaling
                scale_ratio = max(target_width / width, target_height / height)

                # Calculate the size after scaling
                resized_width = int(width * scale_ratio)
                resized_height = int(height * scale_ratio)

                # Resize image
                output_image = input_image.resize((resized_width, resized_height))

                # Create the target image and center the resized image
                resized_image = Image.new(
                    "RGB", (target_width, target_height), (255, 255, 255)
                )
                left = (target_width - resized_width) // 2
                top = (target_height - resized_height) // 2
                resized_image.paste(output_image, (left, top))
            elif args.image_conversion_mode == "cut":
                box = (0, 0, width, height)

                resized_image = ImageOps.pad(
                    input_image.crop(box),
                    size=(target_width, target_height),
                    color=(255, 255, 255),
                    centering=(0.5, 0.5),
                )
            input_image.close()

            # Apply enhancements (contrast and saturation)
            enhancer = ImageEnhance.Brightness(resized_image)
            enhanced_image = enhancer.enhance(args.brightness)

            enhancer = ImageEnhance.Contrast(enhanced_image)
            enhanced_image = enhancer.enhance(args.contrast)

            enhancer = ImageEnhance.Color(enhanced_image)
            enhanced_image = enhancer.enhance(args.saturation)

            # Add edge enhancement
            enhanced_image = enhanced_image.filter(ImageFilter.EDGE_ENHANCE)

            # Add noise reduction
            enhanced_image = enhanced_image.filter(ImageFilter.SMOOTH)

            # Add sharpening for better detail visibility
            enhanced_image = enhanced_image.filter(ImageFilter.SHARPEN)

            if args.show_date:
                apply_date_to_image(input_image, enhanced_image, args)

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
            quantized_image = enhanced_image.quantize(
                dither=args.dithering_algorithm,
                palette=pal_image).convert("RGB")

            # Save output image to pic/ subfolder with sequentially numbered filename
            sequential_name = f"{counter:06d}.bmp"  # Format as 000001.bmp
            output_filename = os.path.join(output_dir , sequential_name)
            quantized_image.save(output_filename)

            # Add to list of converted files
            converted_files.append(output_filename)

            # Update progress instead of printing
            pbar.update(1)
            pbar.set_postfix(file=os.path.basename(input_filename), status="Success")

            # Increment counter for next file
            counter += 1
        except Exception as e:
            # Show errors even with progress bar, but use pbar.write for cleaner output
            pbar.update(1)
            pbar.set_postfix(file=os.path.basename(input_filename), status="Error")
            pbar.write(f"Error processing {input_filename}: {e}")
            raise

    # Close the progress bar
    pbar.close()

    # Write the list of converted files to fileList.txt
    if converted_files:
        with open(os.path.join(args.disk_path, "fileList.txt"), "w") as f:
            for file in converted_files:
                f.write(f"{file}\n")
        pbar.write(f"Created fileList.txt with {len(converted_files)} entries")


if __name__ == "__main__":
    main()