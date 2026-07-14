import os
import re
import asyncio
import shutil
import zipfile
import logging
import time
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from PIL import Image

from api_clients import get_ai_client, BaseClient
from config import config, build_dynamic_prompt, build_expansion_prompt, DEFAULT_ENABLED_DIMS, END_MARKER

logger = logging.getLogger(__name__)

@dataclass
class ProcessResult:
    filename: str 
    prompt: str
    success: bool
    error: Optional[str] = None

def clean_old_temp_dirs(parent_dir: str, max_age_seconds: int = 600):
    try:
        now = time.time()
        for item in Path(parent_dir).iterdir():
            if item.is_dir() and item.name.startswith("batch_"):
                if now - item.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
    except Exception: pass

def compress_image_for_api(src_path: str, dst_path: str, max_size: int = 1024, quality: int = 80):
    try:
        with Image.open(src_path) as img:
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img.save(dst_path, "JPEG", quality=quality, optimize=True)
    except Exception:
        shutil.copy2(src_path, dst_path)

def parse_batch_response(text: str, expected_count: int) -> List[str]:
    junk_patterns = [r'已确认.*?请上传图片[。.]?', r'好的.*?无审核模式.*?\n', r'Understood.*?Ready.*?\n']
    for pat in junk_patterns: text = re.sub(pat, '', text, flags=re.IGNORECASE)
    text = text.replace('\r\n', '\n').strip()
    
    split_pattern = r'(?:---\s*IMAGE\s*\d+\s*---|\[\s*IMAGE\s*\d+\s*\]|(?:\*\*|###?)?\s*(?:图像|图片|图|第)\s*\d+\s*(?:张图(?:片)?)?\s*(?:描述)?\s*(?:\*\*|：|:|)*)'
    parts = re.split(split_pattern, text, flags=re.IGNORECASE)
    prompts = [p.strip() for p in parts if p.strip()]

    if len(prompts) > expected_count: prompts = prompts[-expected_count:]

    result = []
    for i in range(expected_count):
        if i < len(prompts): result.append(prompts[i].lstrip('*•-\t ').strip())
        else: result.append("Error: ⚠️ AI 未返回该图片的描述，或中途被截断。请尝试调高 Roll 次数。")
    return result


class BatchProcessor:
    def __init__(self, ai_client=None, custom_prompt=None, images_per_request=None, 
                 nsfw=False, nsfw_max_rolls=3, enabled_dims=None, portrait=False, portrait_suffix=""):
        self.client = ai_client or get_ai_client()
        self.custom_prompt = custom_prompt
        self.images_per_request = images_per_request or config.IMAGES_PER_REQUEST
        self.nsfw = nsfw
        self.nsfw_max_rolls = nsfw_max_rolls
        self.enabled_dims = enabled_dims or DEFAULT_ENABLED_DIMS
        self.portrait = portrait
        self.portrait_suffix = portrait_suffix

    async def process_batch(self, image_paths, output_dir):
        temp_compress_dir = tempfile.mkdtemp()
        chunk_size = self.images_per_request
        chunks = [image_paths[i:i + chunk_size] for i in range(0, len(image_paths), chunk_size)]
        results = []

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"处理第 {chunk_idx+1}/{len(chunks)} 组 ({len(chunk)} 张)")

            if self.custom_prompt:
                effective_prompt = self.custom_prompt + f"\n\n【极度重要】本次共 {len(chunk)} 张图片。你必须使用 [IMAGE X] 格式严格分隔输出！"
                if self.nsfw: effective_prompt += f"\n【防截断判定】完成所有输出后，必须在新的一行输出暗号：“{END_MARKER}”"
            else:
                effective_prompt = build_dynamic_prompt(self.enabled_dims, self.nsfw, len(chunk), self.portrait, self.portrait_suffix)

            compressed = []
            for idx, img_path in enumerate(chunk):
                comp = os.path.join(temp_compress_dir, f"comp_{chunk_idx}_{idx}.jpg")
                compress_image_for_api(img_path, comp)
                compressed.append(comp)

            raw_response = ""
            max_attempts = self.nsfw_max_rolls + 1 if self.nsfw else 1
            
            for attempt in range(max_attempts):
                try:
                    raw_response = await self.client.analyze_images(compressed, effective_prompt, nsfw=self.nsfw)
                    if self.nsfw:
                        if END_MARKER in raw_response:
                            raw_response = raw_response.replace(END_MARKER, "") 
                            break
                        else:
                            if attempt < self.nsfw_max_rolls:
                                logger.warning(f"⚠️ 第 {chunk_idx+1} 组未检测到暗号，触发重试(Roll) {attempt+1}/{self.nsfw_max_rolls}...")
                                await asyncio.sleep(1.5)
                                continue
                    else:
                        break
                except Exception as e:
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)
                        continue
                    raise e

            try:
                prompts = parse_batch_response(raw_response, len(chunk))
                for i, img_path in enumerate(chunk):
                    original_name = Path(img_path).name  
                    stem_name = Path(img_path).stem      
                    dst_img = os.path.join(output_dir, original_name)
                    shutil.copy2(img_path, dst_img)
                    dst_txt = os.path.join(output_dir, f"{stem_name}.txt")
                    with open(dst_txt, "w", encoding="utf-8") as f: f.write(prompts[i])
                    results.append(ProcessResult(filename=original_name, prompt=prompts[i], success=True))
            except Exception as e:
                for img_path in chunk:
                    results.append(ProcessResult(filename=Path(img_path).name, prompt="", success=False, error=str(e)))
            
            await asyncio.sleep(0.5)

        zip_path_all = f"{output_dir}_all.zip"
        zip_path_txt = f"{output_dir}_only_txt.zip"

        with zipfile.ZipFile(zip_path_all, "w", zipfile.ZIP_DEFLATED) as zf_all, \
             zipfile.ZipFile(zip_path_txt, "w", zipfile.ZIP_DEFLATED) as zf_txt:
            for root, _, files in os.walk(output_dir):
                for f in sorted(files):
                    if f.endswith(".zip"): continue
                    file_path = os.path.join(root, f)
                    zf_all.write(file_path, f)
                    if f.endswith(".txt"): zf_txt.write(file_path, f)

        shutil.rmtree(temp_compress_dir, ignore_errors=True)
        return [zip_path_all, zip_path_txt], results


def process_batch_sync(input_paths, provider=None, api_key=None, base_url=None, model=None,
                       custom_prompt=None, images_per_request=None, nsfw=False, nsfw_max_rolls=3,
                       enabled_dims=None, portrait=False, portrait_suffix=""):
    clean_old_temp_dirs(config.OUTPUT_DIR)
    timestamp = int(time.time())
    task_output_dir = os.path.join(config.OUTPUT_DIR, f"batch_{timestamp}")
    os.makedirs(task_output_dir, exist_ok=True)
    final_image_paths = []
    temp_extract_dir = None

    if len(input_paths) == 1 and input_paths[0].endswith(".zip"):
        temp_extract_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(input_paths[0], 'r') as zr:
                for fi in zr.infolist():
                    if fi.filename.startswith('__MACOSX') or fi.filename.startswith('.'): continue
                    if Path(fi.filename).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']:
                        fn = Path(fi.filename).name
                        ep = os.path.join(temp_extract_dir, fn)
                        if os.path.exists(ep): ep = os.path.join(temp_extract_dir, f"{int(time.time()*1000)}_{fn}")
                        with zr.open(fi) as src, open(ep, "wb") as dst: shutil.copyfileobj(src, dst)
                        final_image_paths.append(ep)
            final_image_paths.sort()
        except Exception as e:
            return None, f"❌ ZIP 解压失败: {e}", []
    else:
        final_image_paths = input_paths

    if not final_image_paths: return None, "❌ 未找到有效图片", []

    client = get_ai_client(provider, api_key, base_url, model)
    processor = BatchProcessor(
        ai_client=client, custom_prompt=custom_prompt, images_per_request=images_per_request, 
        nsfw=nsfw, nsfw_max_rolls=nsfw_max_rolls, enabled_dims=enabled_dims or DEFAULT_ENABLED_DIMS,
        portrait=portrait, portrait_suffix=portrait_suffix
    )

    loop = asyncio.new_event_loop()
    try: zip_paths, results = loop.run_until_complete(processor.process_batch(final_image_paths, task_output_dir))
    finally:
        loop.close()
        if temp_extract_dir and os.path.exists(temp_extract_dir): shutil.rmtree(temp_extract_dir, ignore_errors=True)

    gallery_data = []
    summary_lines = []
    for idx, r in enumerate(results, 1):
        saved_path = os.path.join(task_output_dir, r.filename)
        if r.success and os.path.exists(saved_path): gallery_data.append((saved_path, f"[{idx}] {r.filename}"))
        status = "✅" if r.success else "❌"
        content = r.prompt if r.success else f"Error: {r.error}"
        summary_lines.append(f"{status} {r.filename}\n{'-'*40}\n{content}\n")

    summary = f"\n{'='*60}\n\n".join(summary_lines)
    return zip_paths, summary, gallery_data

# ==================== 新增：标签扩写核心逻辑 ====================
def expand_tags_sync(tags, provider=None, api_key=None, base_url=None, model=None,
                     nsfw=False, nsfw_max_rolls=3, enabled_dims=None, portrait=False, portrait_suffix=""):
    if not tags.strip(): return "❌ 请先输入需要扩写的标签或元素"

    client = get_ai_client(provider, api_key, base_url, model)
    effective_prompt = build_expansion_prompt(enabled_dims or DEFAULT_ENABLED_DIMS, nsfw, portrait, portrait_suffix)
    full_prompt = f"{effective_prompt}\n\n【用户输入的待扩写标签/元素】：\n{tags}"

    async def _run():
        max_attempts = nsfw_max_rolls + 1 if nsfw else 1
        raw_response = ""
        for attempt in range(max_attempts):
            try:
                # 传入空图片列表，客户端会当做纯文本请求处理
                raw_response = await client.analyze_images([], full_prompt, nsfw=nsfw)
                if nsfw:
                    if END_MARKER in raw_response:
                        raw_response = raw_response.replace(END_MARKER, "")
                        break
                    else:
                        if attempt < nsfw_max_rolls:
                            await asyncio.sleep(1.5)
                            continue
                break
            except Exception as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                return f"❌ 扩写失败: {str(e)}"

        # 清理可能残留的图片模板垃圾格式
        junk = [r'已确认.*?\n', r'好的.*?\n', r'Understood.*?\n', r'■', r'\[IMAGE 1\]\n?']
        for pat in junk: raw_response = re.sub(pat, '', raw_response, flags=re.IGNORECASE)
        return raw_response.strip()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
