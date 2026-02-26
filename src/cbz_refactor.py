import os
import csv
import zipfile
import shutil
import re
import argparse
import logging
from pathlib import Path
from datetime import datetime
from io import BytesIO

def is_special_file(filename):
    """Check if a CBZ file is a 'special' based on naming pattern SP01, SP02, etc."""
    # Matches patterns like SP01, SP02, etc. (case-insensitive)
    pattern = r'(?i)SP\d{2}'
    return bool(re.search(pattern, filename))

def is_volume_file(filename):
    """Check if a CBZ file already has a volume pattern VXXX or V001, V002, etc."""
    # Matches patterns like V001, V01, V1, etc. (case-insensitive)
    pattern = r'(?i)V\d+'
    return bool(re.search(pattern, filename))

def extract_volume_number(filename):
    """Extract the volume number from a filename with VXXX pattern. Returns None if not found."""
    # Matches patterns like V001, V01, V1, etc. (case-insensitive)
    pattern = r'(?i)V(\d+)'
    match = re.search(pattern, filename)
    if match:
        return int(match.group(1))
    return None

def setup_logging(base_path):
    """Setup logging to file and console."""
    log_file = Path(base_path) / f"cbz_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Create logger
    logger = logging.getLogger('cbz_refactor')
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def parse_batch_sizes(batch_str):
    """
    Parse batch size string. Can be either:
    - Single number: "5"
    - Multiple numbers separated by comma: "3,4,5,3"
    Returns tuple of (batch_sizes_list, is_repeating)
    """
    batch_str = batch_str.strip()
    
    # Check if it contains commas (multiple values)
    if ',' in batch_str:
        try:
            sizes = [int(x.strip()) for x in batch_str.split(',')]
            return sizes, False
        except ValueError:
            raise ValueError(f"Invalid batch sizes: {batch_str}")
    else:
        # Single number - repeat indefinitely
        try:
            size = int(batch_str)
            return [size], True
        except ValueError:
            raise ValueError(f"Invalid batch size: {batch_str}")

def parse_bool(value, default=True):
    """
    Parse a boolean value from CSV. Returns default if empty/missing.
    Accepts: true/false, yes/no, 1/0, t/f, y/n (case-insensitive)
    """
    if not value or not value.strip():
        return default
    
    value = value.strip().lower()
    
    if value in ('true', 'yes', '1', 't', 'y'):
        return True
    elif value in ('false', 'no', '0', 'f', 'n'):
        return False
    else:
        raise ValueError(f"Invalid boolean value: {value}")

def calculate_batches(num_files, batch_sizes, is_repeating, no_extra, logger):
    """
    Calculate how files should be batched.
    Returns list of batch sizes to use.
    If no_extra is True, doesn't create partial batches for remaining files.
    """
    if is_repeating:
        # Simple case: repeat the single size
        batch_size = batch_sizes[0]
        if no_extra:
            # Only create complete batches
            num_batches = num_files // batch_size
            if num_files % batch_size != 0:
                remaining = num_files % batch_size
                logger.info(f"With no-extra: {remaining} files will remain as individual CBZ files")
        else:
            # Create all batches including partial last one
            num_batches = (num_files + batch_size - 1) // batch_size
        return [batch_size] * num_batches
    
    # Multiple specified sizes
    total_specified = sum(batch_sizes)
    
    if num_files <= total_specified:
        # We have enough or exact match with specified sizes
        result = []
        remaining = num_files
        for size in batch_sizes:
            if remaining <= 0:
                break
            result.append(min(size, remaining))
            remaining -= size
        return result
    
    # We have more files than specified
    if no_extra:
        # Only use the specified batches, leave remaining files as-is
        remaining = num_files - total_specified
        logger.info(f"With no-extra: {remaining} files will remain as individual CBZ files")
        return batch_sizes.copy()
    
    # Original behavior: create additional batches for remaining files
    remaining = num_files - total_specified
    avg_size = sum(batch_sizes) // len(batch_sizes)
    
    logger.info(f"Remaining chapters: {remaining}, average chunk size: {avg_size}")
    
    # Create batches for remaining files using average size
    result = batch_sizes.copy()
    while remaining > 0:
        if remaining > avg_size:
            result.append(avg_size)
            remaining -= avg_size
        else:
            result.append(remaining)
            remaining = 0
    
    return result

def extract_cbz_to_memory(cbz_path, logger):
    """Extract a CBZ file to memory and return list of (filename, data) tuples."""
    try:
        images = []
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
        
        with zipfile.ZipFile(cbz_path, 'r') as zip_ref:
            # Get all files in the archive
            for file_info in zip_ref.filelist:
                filename_lower = file_info.filename.lower()
                
                # Skip ComicInfo.xml and any XML files
                if filename_lower == 'comicinfo.xml' or filename_lower.endswith('.xml'):
                    continue
                
                if Path(file_info.filename).suffix.lower() in image_extensions:
                    # Read file data into memory
                    file_data = zip_ref.read(file_info.filename)
                    images.append((file_info.filename, file_data))
        
        # Sort by filename
        images.sort(key=lambda x: x[0])
        logger.info(f"Extracted to memory: {cbz_path.name} ({len(images)} images)")
        return images
    except Exception as e:
        logger.error(f"Failed to extract {cbz_path.name}: {str(e)}")
        raise

def create_cbz_from_memory(output_path, image_data_list, logger):
    """Create a CBZ file from in-memory image data with consecutive naming."""
    try:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, (original_name, data) in enumerate(image_data_list, start=1):
                ext = Path(original_name).suffix
                new_name = f"page_{idx:03d}{ext}"
                
                # Write directly from memory to zip
                zipf.writestr(new_name, data)
        
        logger.info(f"Created: {output_path.name} ({len(image_data_list)} pages)")
    except Exception as e:
        logger.error(f"Failed to create {output_path.name}: {str(e)}")
        raise

def process_directory(base_path, folder_name, batch_sizes_str, no_extra, avoid_volumes, delete_originals, logger):
    """Process a single directory according to the refactoring rules."""
    folder_path = Path(base_path) / folder_name
    
    if not folder_path.exists():
        logger.error(f"Folder '{folder_name}' does not exist. Skipping.")
        return
    
    # Parse batch sizes
    try:
        batch_sizes, is_repeating = parse_batch_sizes(batch_sizes_str)
        logger.info(f"Processing: {folder_name} (batch: {batch_sizes_str}, no-extra: {no_extra}, avoid-volumes: {avoid_volumes}, delete: {delete_originals})")
    except ValueError as e:
        logger.error(f"Invalid batch configuration for '{folder_name}': {str(e)}")
        return
    
    # Get all CBZ files
    cbz_files = sorted([f for f in folder_path.glob("*.cbz")])
    
    if not cbz_files:
        logger.info(f"No CBZ files found in {folder_name}")
        return
    
    # Separate special files and volume files
    regular_files = []
    special_files = []
    volume_files = []
    
    for cbz in cbz_files:
        if is_special_file(cbz.name):
            special_files.append(cbz)
        elif avoid_volumes and is_volume_file(cbz.name):
            volume_files.append(cbz)
        else:
            regular_files.append(cbz)
    
    # Move special files to Specials subfolder
    if special_files:
        specials_dir = folder_path / "Specials"
        specials_dir.mkdir(exist_ok=True)
        
        for special in special_files:
            try:
                dest = specials_dir / special.name
                shutil.move(str(special), str(dest))
                logger.info(f"Moved to Specials: {special.name}")
            except Exception as e:
                logger.error(f"Failed to move {special.name} to Specials: {str(e)}")
    
    # Log volume files that are being skipped
    if volume_files:
        logger.info(f"Skipping {len(volume_files)} files with volume pattern: {[f.name for f in volume_files]}")
    
    # Determine starting volume number
    volume_counter = 1
    if avoid_volumes and volume_files:
        # Find the highest volume number among existing volume files
        max_volume = 0
        for vol_file in volume_files:
            vol_num = extract_volume_number(vol_file.name)
            if vol_num is not None and vol_num > max_volume:
                max_volume = vol_num
        
        if max_volume > 0:
            volume_counter = max_volume + 1
            logger.info(f"Found existing volumes up to V{max_volume:03d}, starting new volumes from V{volume_counter:03d}")
    
    if not regular_files:
        logger.info(f"No regular CBZ files to process in {folder_name}")
        return
    
    # Calculate actual batches to use
    actual_batches = calculate_batches(len(regular_files), batch_sizes, is_repeating, no_extra, logger)
    logger.info(f"Will create {len(actual_batches)} volumes with sizes: {actual_batches}")
    
    # Process files according to calculated batches
    file_index = 0
    
    for batch_size in actual_batches:
        batch = regular_files[file_index:file_index + batch_size]
        file_index += batch_size
        
        logger.info(f"Processing batch {volume_counter} ({len(batch)} files)...")
        
        all_images = []
        
        # Extract all CBZ files in this batch to memory
        for cbz_file in batch:
            try:
                images = extract_cbz_to_memory(cbz_file, logger)
                all_images.extend(images)
            except Exception as e:
                logger.error(f"Error processing {cbz_file.name}: {str(e)}")
                continue
        
        if not all_images:
            logger.error(f"No images found in batch {volume_counter}. Skipping.")
            volume_counter += 1
            continue
        
        # Create new volume with consecutive page numbering
        output_name = f"{folder_name} V{volume_counter:03d}.cbz"
        output_path = folder_path / output_name
        
        try:
            create_cbz_from_memory(output_path, all_images, logger)
            
            # Delete original CBZ files if requested
            if delete_originals:
                for cbz_file in batch:
                    try:
                        cbz_file.unlink()
                        logger.info(f"Deleted: {cbz_file.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {cbz_file.name}: {str(e)}")
            
            volume_counter += 1
        except Exception as e:
            logger.error(f"Failed to create volume {volume_counter}: {str(e)}")
        finally:
            # Clear memory
            all_images.clear()
    
    # Log info about remaining files if any
    if file_index < len(regular_files):
        remaining_files = regular_files[file_index:]
        logger.info(f"Left {len(remaining_files)} files as individual CBZ files: {[f.name for f in remaining_files]}")

def main(base_directory):
    """Main function to orchestrate the refactoring process."""
    base_path = Path(base_directory)
    csv_file = base_path / "to_refactor.csv"
    
    # Setup logging
    logger = setup_logging(base_path)
    logger.info("=== CBZ Refactoring Script Started (CSV-Configured Mode) ===")
    logger.info(f"Base directory: {base_directory}")
    logger.info(f"Default settings: no-extra=True, avoid-volumes=True, delete=True")
    
    if not csv_file.exists():
        logger.error(f"'to_refactor.csv' not found in {base_directory}")
        return
    
    logger.info(f"Reading configuration from: {csv_file}")
    
    # Read CSV file
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row_num, row in enumerate(reader, start=1):
                if len(row) < 1:
                    logger.error(f"Invalid row {row_num}: {row}. Skipping.")
                    continue
                
                folder_name = row[0].strip()
                
                # Check if batch_sizes is provided
                if len(row) < 2 or not row[1].strip():
                    logger.info(f"No batch size specified for '{folder_name}'. Skipping.")
                    continue
                
                batch_sizes_str = row[1].strip()
                
                # Parse optional columns with defaults = True
                try:
                    no_extra = parse_bool(row[2], default=True) if len(row) > 2 else True
                    avoid_volumes = parse_bool(row[3], default=True) if len(row) > 3 else True
                    delete_originals = parse_bool(row[4], default=True) if len(row) > 4 else True
                    ignore = parse_bool(row[5], default=False) if len(row) > 5 else False  # Default is False (don't ignore)
                except ValueError as e:
                    logger.error(f"Invalid boolean value in row {row_num}: {str(e)}. Using defaults.")
                    no_extra = True
                    avoid_volumes = True
                    delete_originals = True
                    ignore = False
                
                # Check if series should be ignored
                if ignore:
                    logger.info(f"Series '{folder_name}' marked as ignored. Skipping.")
                    continue
                
                process_directory(base_path, folder_name, batch_sizes_str, no_extra, avoid_volumes, delete_originals, logger)
    except Exception as e:
        logger.error(f"Error reading CSV file: {str(e)}")
        return
    
    logger.info("=== Refactoring complete! ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Refactor CBZ files based on CSV configuration (in-memory processing)')
    parser.add_argument('directory', help='Base directory containing to_refactor.csv and folders to process')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory")
        exit(1)
    
    main(args.directory)
