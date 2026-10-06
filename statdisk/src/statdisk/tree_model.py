"""
Data model representing the filesystem tree hierarchy.
Supports fast traversal, aggregation, and querying.
"""

import os
import math
import time
from typing import List, Optional, Dict, Any

# Common file extension categorization
EXT_CATEGORIES = {
    # Media / Video
    '.mp4': 'Video', '.mkv': 'Video', '.avi': 'Video', '.mov': 'Video',
    '.webm': 'Video', '.flv': 'Video', '.wmv': 'Video', '.m4v': 'Video',
    # Audio
    '.mp3': 'Audio', '.flac': 'Audio', '.wav': 'Audio', '.ogg': 'Audio',
    '.m4a': 'Audio', '.aac': 'Audio', '.opus': 'Audio', '.wma': 'Audio',
    # Images
    '.png': 'Image', '.jpg': 'Image', '.jpeg': 'Image', '.gif': 'Image',
    '.svg': 'Image', '.webp': 'Image', '.bmp': 'Image', '.ico': 'Image',
    '.tiff': 'Image', '.raw': 'Image', '.psd': 'Image',
    # Documents
    '.pdf': 'Document', '.docx': 'Document', '.doc': 'Document',
    '.xlsx': 'Document', '.xls': 'Document', '.pptx': 'Document',
    '.ppt': 'Document', '.odt': 'Document', '.ods': 'Document',
    '.txt': 'Document', '.md': 'Document', '.rst': 'Document',
    '.epub': 'Document',
    # Archives / Compressed
    '.zip': 'Archive', '.tar': 'Archive', '.gz': 'Archive', '.bz2': 'Archive',
    '.xz': 'Archive', '.7z': 'Archive', '.rar': 'Archive', '.iso': 'Archive',
    '.deb': 'Archive', '.rpm': 'Archive', '.AppImage': 'Archive',
    # Data & Statistics (Stat Major favorite!)
    '.csv': 'Dataset', '.tsv': 'Dataset', '.json': 'Dataset',
    '.parquet': 'Dataset', '.arrow': 'Dataset', '.feather': 'Dataset',
    '.sqlite': 'Database', '.db': 'Database', '.sqlite3': 'Database',
    '.sql': 'Database', '.rdata': 'Dataset', '.rds': 'Dataset',
    '.dta': 'Dataset', '.sav': 'Dataset', '.sas7bdat': 'Dataset',
    '.hdf5': 'Dataset', '.h5': 'Dataset', '.npy': 'Dataset', '.npz': 'Dataset',
    # Code & Development
    '.py': 'Code', '.c': 'Code', '.cpp': 'Code', '.h': 'Code',
    '.hpp': 'Code', '.rs': 'Code', '.go': 'Code', '.java': 'Code',
    '.js': 'Code', '.ts': 'Code', '.html': 'Code', '.css': 'Code',
    '.sh': 'Code', '.bash': 'Code', '.rb': 'Code', '.php': 'Code',
    '.yaml': 'Config', '.yml': 'Config', '.toml': 'Config', '.xml': 'Config',
    '.ini': 'Config', '.conf': 'Config',
    # Binaries / Executables
    '.so': 'Binary', '.bin': 'Binary', '.exe': 'Binary', '.dll': 'Binary',
    '.o': 'Binary', '.a': 'Binary',
}


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable string with binary units (IEC standard)."""
    if num_bytes < 0:
        return "0 B"
    if num_bytes == 0:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    idx = 0
    val = float(num_bytes)
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(val)} B"
    return f"{val:.2f} {units[idx]}"


def categorize_file(name: str, ext: str) -> str:
    """Classify file into high-level category."""
    if ext in EXT_CATEGORIES:
        return EXT_CATEGORIES[ext]
    if name.startswith('.'):
        return 'Hidden / Config'
    return 'Other'


class FileNode:
    """Represents a node in the filesystem tree (directory or file)."""
    __slots__ = (
        'path', 'name', 'is_dir', 'size', 'mtime',
        'extension', 'category', 'children', 'parent',
        'file_count', 'dir_count'
    )

    def __init__(self, path: str, name: str, is_dir: bool, size: int = 0, mtime: float = 0.0):
        self.path: str = path
        self.name: str = name
        self.is_dir: bool = is_dir
        self.size: int = size
        self.mtime: float = mtime
        self.children: List['FileNode'] = []
        self.parent: Optional['FileNode'] = None
        self.file_count: int = 0 if is_dir else 1
        self.dir_count: int = 1 if is_dir else 0

        if not is_dir:
            _, ext = os.path.splitext(name)
            self.extension: str = ext.lower()
            self.category: str = categorize_file(name, self.extension)
        else:
            self.extension = ''
            self.category = 'Folder'

    def add_child(self, child: 'FileNode') -> None:
        """Add a child node and establish parent reference."""
        child.parent = self
        self.children.append(child)

    def sort_children(self, recursive: bool = True) -> None:
        """Sort children in descending order of size."""
        self.children.sort(key=lambda c: c.size, reverse=True)
        if recursive:
            for child in self.children:
                if child.is_dir:
                    child.sort_children(recursive=True)

    @property
    def human_size(self) -> str:
        return format_bytes(self.size)

    @property
    def formatted_mtime(self) -> str:
        if self.mtime <= 0:
            return "Unknown"
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.mtime))
        except (ValueError, OSError):
            return "Unknown"

    def get_ancestors(self) -> List['FileNode']:
        """Return list of ancestor nodes from root down to self."""
        chain = []
        curr: Optional['FileNode'] = self
        while curr is not None:
            chain.append(curr)
            curr = curr.parent
        chain.reverse()
        return chain

    def collect_all_files(self) -> List['FileNode']:
        """Recursively collect all leaf file nodes."""
        files = []
        stack = [self]
        while stack:
            curr = stack.pop()
            if curr.is_dir:
                stack.extend(curr.children)
            else:
                files.append(curr)
        return files

    def find_node(self, target_path: str) -> Optional['FileNode']:
        """Find a node by absolute path in this subtree."""
        if self.path == target_path:
            return self
        if not self.is_dir:
            return None
        for child in self.children:
            if child.is_dir:
                if target_path == child.path or target_path.startswith(child.path + os.sep):
                    res = child.find_node(target_path)
                    if res:
                        return res
            elif child.path == target_path:
                return child
        return None
