"""
Bluesky syndication service for PosseTool.
"""

import os
import re
import tempfile
import urllib.parse
import unicodedata
import requests
import html
from pathlib import Path
from PIL import Image, ImageOps
from io import BytesIO

from .base import SyndicationService
import config
from text_processing import clean_html_text, extract_first_meaningful_paragraph


class BlueskyService(SyndicationService):
    """Bluesky syndication service using atproto."""
    
    def __init__(self, credentials, test_mode=False):
        super().__init__(credentials, test_mode)
        self.client = None
    
    def can_handle(self, trigger_tag):
        return trigger_tag == 'bsky'
    
    def authenticate(self):
        """Authenticate with Bluesky using credentials."""
        try:
            from atproto import Client
            self.client = Client()
            self.client.login(
                self.credentials.get('identifier'),
                self.credentials.get('password')
            )
            return True
        except Exception as e:
            print(f"Bluesky authentication failed: {e}")
            return False
    
    def _prepare_post_text(self, entry):
        """Prepare the post text and facets."""
        url = entry.get('url', '')
        
        # Calculate available space for text (reserve space for URL first)
        if url:
            available_space = config.BLUESKY_CHAR_LIMIT - len(url) - 2  # 2 for "\n\n"
        else:
            available_space = config.BLUESKY_CHAR_LIMIT
        
        # Extract first meaningful paragraph from content with the available space
        content = entry.get('content', '')
        post_text = extract_first_meaningful_paragraph(content, available_space)
        
        # If no meaningful paragraph found, fall back to summary
        if not post_text:
            summary = clean_html_text(entry.get('summary', ''))
            post_text = unicodedata.normalize('NFC', summary)
            # Truncate summary if needed
            if len(post_text) > available_space:
                post_text = post_text[:available_space-3] + "..."
        
        # Add URL if available
        facets = []
        if url:
            post_text += f"\n\n{url}"
            facets.append(self._create_link_facet(post_text, url))
        
        return post_text, facets
    
    def _create_link_facet(self, post_text, url):
        """Create a link facet for the given URL."""
        link_start = len(post_text) - len(url)
        link_end = len(post_text)
        return {
            "index": {
                "byteStart": link_start,
                "byteEnd": link_end
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url
            }]
        }
    
    def _extract_image_from_content(self, content):
        """Extract the first image URL from HTML content."""
        if not content:
            return None
        
        # Unescape HTML entities
        unescaped_content = html.unescape(content)
        
        # Find the first <img> tag
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', unescaped_content)
        if img_match:
            return img_match.group(1)
        return None
    
    def _process_image(self, image_url):
        """Download, process, and upload an image to Bluesky."""
        if not image_url:
            return None
        
        temp_image_path = None
        try:
            # Download the image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Determine file extension
            extension = self._get_image_extension(image_url, response.headers)
            
            # Create temporary file
            temp_fd, temp_image_path = tempfile.mkstemp(suffix=extension)
            os.close(temp_fd)
            
            # Process and save image
            self._resize_and_compress_image(response.content, temp_image_path)
            
            # Upload to Bluesky
            with open(temp_image_path, 'rb') as f:
                img_data = f.read()
            upload_response = self.client.upload_blob(img_data)
            return upload_response.blob
            
        except Exception as e:
            print(f"Warning: Failed to upload image {image_url}: {e}")
            return None
        finally:
            # Clean up temporary file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                except Exception as e:
                    print(f"Warning: Failed to delete temporary image {temp_image_path}: {e}")
    
    def _get_image_extension(self, image_url, headers):
        """Determine the file extension from URL or content type."""
        # Try to get extension from URL
        parsed_url = urllib.parse.urlparse(image_url)
        url_path = Path(parsed_url.path)
        extension = url_path.suffix
        
        # If no extension in URL, try to get from content type
        if not extension:
            content_type = headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            elif 'gif' in content_type:
                extension = '.gif'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                extension = '.jpg'  # Default fallback
        
        return extension
    
    def _resize_and_compress_image(self, image_data, output_path):
        """Resize and compress image to meet Bluesky requirements."""
        try:
            # Open image from bytes
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Calculate new dimensions while maintaining aspect ratio
            width, height = image.size
            target_width = config.BLUESKY_IMAGE_TARGET_WIDTH
            target_height = config.BLUESKY_IMAGE_TARGET_HEIGHT
            
            # Calculate scaling factor
            scale_w = target_width / width
            scale_h = target_height / height
            scale = min(scale_w, scale_h)
            
            # Only resize if image is larger than target
            if scale < 1:
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save with progressive quality reduction until file size is acceptable
            quality = config.BLUESKY_IMAGE_QUALITY_START
            output_buffer = BytesIO()
            
            while quality >= config.BLUESKY_IMAGE_QUALITY_MIN:
                output_buffer.seek(0)
                output_buffer.truncate()
                image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                
                if output_buffer.tell() <= config.BLUESKY_IMAGE_MAX_SIZE:
                    break
                quality -= config.BLUESKY_IMAGE_QUALITY_STEP
            
            # Save the processed image
            with open(output_path, 'wb') as f:
                f.write(output_buffer.getvalue())
                
        except Exception as e:
            print(f"Warning: Failed to process image: {e}")
            # Fallback: save original image
            with open(output_path, 'wb') as f:
                f.write(image_data)
    
    def _create_external_embed(self, url, entry, summary, image_blob_ref):
        """Create an external embed for the URL."""
        from atproto import models
        
        external_link = models.AppBskyEmbedExternal.External(
            uri=url,
            title=entry.get('title', ''),
            description=summary[:config.BLUESKY_DESCRIPTION_LIMIT] if summary else '',
            thumb=image_blob_ref
        )
        
        return models.AppBskyEmbedExternal.Main(external=external_link)
    
    def post(self, entry):
        """Post a skeet to Bluesky."""
        if not self.client and not self.test_mode:
            if not self.authenticate():
                return False
        
        try:
            # Prepare post text and facets
            post_text, facets = self._prepare_post_text(entry)
            
            if self.test_mode:
                self._log_test_post("Bluesky", entry['title'], post_text)
                return True
            
            # Handle posting with or without embed
            url = entry.get('url', '')
            if url:
                # Extract and process image
                content = entry.get('content', '')
                image_url = self._extract_image_from_content(content)
                image_blob_ref = self._process_image(image_url) if image_url else None
                
                # Create embed and post
                # Use original summary for the embed, not the post text
                original_summary = clean_html_text(entry.get('summary', ''))
                embed = self._create_external_embed(url, entry, original_summary, image_blob_ref)
                self.client.send_post(text=post_text, facets=facets, embed=embed)
            else:
                # Post without embed
                self.client.send_post(text=post_text, facets=facets)
            
            print(f"Posted to Bluesky: {entry['title']}")
            return True
            
        except Exception as e:
            if self.test_mode:
                self._log_test_error("Bluesky", e)
                return False
            else:
                print(f"Failed to post to Bluesky: {e}")
                return False 