import os
import mimetypes
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from urllib.parse import quote, unquote

router = APIRouter(prefix="/logs", tags=["logs"])

LOGS_DIR = Path("./logs")

# Ensure logs directory exists on import
LOGS_DIR.mkdir(exist_ok=True)


def get_file_browser_html(current_path: Path, request_url: str) -> str:
    """Generate HTML file browser with right-click delete functionality."""
    
    # Calculate relative path from logs root
    try:
        rel_path = current_path.relative_to(LOGS_DIR)
        breadcrumb = str(rel_path) if str(rel_path) != "." else ""
    except ValueError:
        breadcrumb = ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Log Files Browser - {breadcrumb or 'Root'}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ margin-bottom: 20px; }}
            .breadcrumb {{ color: #666; margin-bottom: 10px; }}
            .controls {{ margin-bottom: 20px; }}
            .delete-all-btn {{ 
                background: #dc3545; color: white; padding: 8px 16px; 
                border: none; border-radius: 4px; cursor: pointer; 
            }}
            .delete-all-btn:hover {{ background: #c82333; }}
            .file-list {{ list-style: none; padding: 0; }}
            .file-item {{ 
                padding: 8px; margin: 2px 0; border-radius: 4px; 
                cursor: pointer; display: flex; justify-content: space-between;
                align-items: center;
            }}
            .file-item:hover {{ background: #f8f9fa; }}
            .file-link {{ text-decoration: none; color: #007bff; flex: 1; }}
            .file-link:hover {{ text-decoration: underline; }}
            .folder-link {{ color: #6f42c1; font-weight: bold; }}
            .file-size {{ color: #666; font-size: 0.9em; margin-left: 10px; }}
            .context-menu {{
                display: none; position: absolute; background: white;
                border: 1px solid #ccc; border-radius: 4px; padding: 5px 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 1000;
            }}
            .context-menu-item {{
                padding: 8px 15px; cursor: pointer; color: #dc3545;
            }}
            .context-menu-item:hover {{ background: #f8f9fa; }}
            .selected {{ background: #e3f2fd !important; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Log Files Browser</h1>
            <div class="breadcrumb">Path: /{breadcrumb}</div>
        </div>
        
        <div class="controls">
            <button class="delete-all-btn" onclick="deleteAllItems()">Delete All</button>
        </div>
        
        <ul class="file-list" id="fileList">
    """
    
    # Add parent directory link if not at root
    if current_path != LOGS_DIR:
        parent_path = current_path.parent
        parent_rel = parent_path.relative_to(LOGS_DIR) if parent_path != LOGS_DIR else ""
        parent_url = f"/logs{'/' + str(parent_rel) if parent_rel else ''}"
        html += f"""
            <li class="file-item">
                <a href="{parent_url}" class="file-link folder-link">📁 ..</a>
            </li>
        """
    
    if current_path.exists():
        items = sorted(current_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        for item in items:
            item_rel = item.relative_to(LOGS_DIR)
            if item.is_dir():
                item_url = f"/logs/{item_rel}"
                html += f"""
                    <li class="file-item" data-filename="{item.name}" data-filepath="{item_rel}" data-type="folder">
                        <a href="{item_url}" class="file-link folder-link">📁 {item.name}</a>
                    </li>
                """
            else:
                file_size = item.stat().st_size
                size_str = format_file_size(file_size)
                item_url = f"/logs/{item_rel}"
                
                # Use different icons for different file types
                icon = "🖼️" if item.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'] else "📄"
                
                html += f"""
                    <li class="file-item" data-filename="{item.name}" data-filepath="{item_rel}">
                        <a href="{item_url}" class="file-link">{icon} {item.name}</a>
                        <span class="file-size">{size_str}</span>
                    </li>
                """
    
    html += """
        </ul>
        
        <div class="context-menu" id="contextMenu">
            <div class="context-menu-item" onclick="deleteSelectedItem()">Delete</div>
        </div>
        
        <script>
            let selectedFile = null;
            
            // Right-click context menu
            document.addEventListener('contextmenu', function(e) {
                const fileItem = e.target.closest('.file-item[data-filename]');
                if (fileItem) {
                    e.preventDefault();
                    selectedFile = fileItem;
                    
                    // Clear previous selection
                    document.querySelectorAll('.file-item').forEach(item => {
                        item.classList.remove('selected');
                    });
                    fileItem.classList.add('selected');
                    
                    const contextMenu = document.getElementById('contextMenu');
                    contextMenu.style.display = 'block';
                    contextMenu.style.left = e.pageX + 'px';
                    contextMenu.style.top = e.pageY + 'px';
                }
            });
            
            // Hide context menu on click elsewhere
            document.addEventListener('click', function() {
                document.getElementById('contextMenu').style.display = 'none';
                document.querySelectorAll('.file-item').forEach(item => {
                    item.classList.remove('selected');
                });
            });
            
            async function deleteSelectedItem() {
                if (!selectedFile) return;
                
                const filepath = selectedFile.dataset.filepath;
                const displayName = selectedFile.dataset.filename;
                const isFolder = selectedFile.dataset.type === 'folder';
                const itemType = isFolder ? 'folder' : 'file';
                
                if (confirm(`Delete ${itemType} "${displayName}"?${isFolder ? ' This will delete all contents!' : ''}`)) {
                    try {
                        const endpoint = isFolder ? `/logs/delete-folder/${encodeURIComponent(filepath)}` : `/logs/delete/${encodeURIComponent(filepath)}`;
                        const response = await fetch(endpoint, {
                            method: 'DELETE'
                        });
                        
                        if (response.ok) {
                            selectedFile.remove();
                            alert(`${itemType.charAt(0).toUpperCase() + itemType.slice(1)} deleted successfully`);
                        } else {
                            const error = await response.json();
                            alert(`Error deleting ${itemType}: ` + error.detail);
                        }
                    } catch (error) {
                        alert(`Error deleting ${itemType}: ` + error.message);
                    }
                }
                
                document.getElementById('contextMenu').style.display = 'none';
            }
            
            async function deleteAllItems() {
                if (confirm('Delete ALL files and folders in current directory? This cannot be undone!')) {
                    try {
                        const response = await fetch('/logs/delete-all', {
                            method: 'DELETE',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({path: window.location.pathname})
                        });
                        
                        if (response.ok) {
                            location.reload();
                        } else {
                            const error = await response.json();
                            alert('Error deleting files: ' + error.detail);
                        }
                    } catch (error) {
                        alert('Error deleting files: ' + error.message);
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    
    return html


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


@router.get("/")
@router.get("/{path:path}")
async def browse_logs(request: Request, path: str = ""):
    """Browse log files and directories."""
    current_path = LOGS_DIR / path if path else LOGS_DIR
    
    # Security check
    try:
        current_path.resolve().relative_to(LOGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Don't create directories - just return 404 if path doesn't exist
    if not current_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    # If it's a file, serve it directly
    if current_path.is_file():
        mime_type, _ = mimetypes.guess_type(str(current_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
        
        # Display inline for non-binary files (no filename = no download prompt)
        # Only force download for known binary types
        binary_types = ('application/octet-stream', 'application/zip', 'application/pdf', 
                       'application/x-', 'video/', 'audio/')
        
        if any(mime_type.startswith(bt) for bt in binary_types):
            return FileResponse(
                path=str(current_path), 
                filename=current_path.name,
                media_type=mime_type
            )
        else:
            return FileResponse(
                path=str(current_path),
                media_type=mime_type
            )
    
    # It's a directory, show the browser
    html_content = get_file_browser_html(current_path, str(request.url))
    return HTMLResponse(content=html_content)


@router.delete("/delete/{filepath:path}")
async def delete_file(filepath: str):
    """Delete a specific file."""
    file_path = LOGS_DIR / filepath
    
    # Security check
    try:
        file_path.resolve().relative_to(LOGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    
    file_path.unlink()
    return JSONResponse({"message": f"File deleted successfully"})


@router.delete("/delete-folder/{folderpath:path}")
async def delete_folder(folderpath: str):
    """Delete a folder and all its contents."""
    import shutil
    
    folder_path = LOGS_DIR / folderpath
    
    # Security check
    try:
        folder_path.resolve().relative_to(LOGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder path")
    
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a folder")
    
    shutil.rmtree(folder_path)
    return JSONResponse({"message": f"Folder deleted successfully"})


@router.delete("/delete-all")
async def delete_all_items(request: Request):
    """Delete all files and folders in the current directory."""
    import shutil
    
    request_data = await request.json()
    path = request_data.get("path", "/logs").replace("/logs", "").lstrip("/")
    
    current_path = LOGS_DIR / path if path else LOGS_DIR
    
    # Security check
    try:
        current_path.resolve().relative_to(LOGS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if not current_path.exists():
        return JSONResponse({"message": "Directory does not exist"})
    
    deleted_files = 0
    deleted_folders = 0
    
    for item in current_path.iterdir():
        if item.is_file():
            item.unlink()
            deleted_files += 1
        elif item.is_dir():
            shutil.rmtree(item)
            deleted_folders += 1
    
    total_deleted = deleted_files + deleted_folders
    message = f"Deleted {deleted_files} files"
    if deleted_folders > 0:
        message += f" and {deleted_folders} folders"
    
    return JSONResponse({"message": message})