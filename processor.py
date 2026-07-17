import os
import re
import hashlib
import asyncio
import shutil
import zipfile
import logging
import time
import tempfile
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass
from PIL import Image

from api_clients import get_ai_client, BaseClient, clean_response
from config import config, build_dynamic_prompt, build_expansion_prompt, DEFAULT_ENABLED_DIMS, END_MARKER

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(config.OUTPUT_DIR, "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class ProcessResult:
    filename: str
    prompt: str
    success: bool
    error: Optional[str] = None
    cached: bool = False


def clean_old_temp_dirs(parent_dir: str, max_age_seconds: int = 600):
    try:
        now = time.time()
        for item in Path(parent_dir).iterdir():
            # 只清理 batch_ 临时目录，_cache 会被保留
            if item.is_dir() and item.name.startswith("batch_"):
                if now - item.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
    except Exception:
        pass


def compress_image_for_api(src_path: str, dst_path: str, max_size: int = 1024, quality: int = 80):
    try:
        with Image.open(src_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img.save(dst_path, "JPEG", quality=quality, optimize=True)
    except Exception:
        shutil.copy2(src_path, dst_path)


def parse_batch_response(text: str, expected_count: int) -> List[str]:
    junk_patterns = [r'已确认.*?请上传图片[。.]?', r'好的.*?无审核模式.*?\n', r'Understood.*?Ready.*?\n']
    for pat in junk_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)
    text = text.replace('\r\n', '\n').strip()

    # 优先只按 [IMAGE N] 分隔，避免误伤结构化维度标题
    split_pattern = r'(?:---\s*IMAGE\s*\d+\s*---|\[\s*IMAGE\s*\d+\s*\])'
    parts = re.split(split_pattern, text, flags=re.IGNORECASE)
    prompts = [p.strip() for p in parts if p.strip()]

    # 兜底：严格切分失败时退回宽松规则
    if len(prompts) <= 1 and expected_count > 1:
        loose_pattern = r'(?:\*\*|###?)?\s*(?:图像|图片|图|第)\s*\d+\s*(?:张图(?:片)?)?\s*(?:描述)?\s*(?:\*\*|：|:|)*'
        parts = re.split(loose_pattern, text, flags=re.IGNORECASE)
        prompts = [p.strip() for p in parts if p.strip()]

    if len(prompts) > expected_count:
        prompts = prompts[-expected_count:]

    result = []
    for i in range(expected_count):
        if i < len(prompts):
            result.append(prompts[i].lstrip('*•-\t ').strip())
        else:
            result.append("Error: ⚠️ AI 未返回该图片的描述，或中途被截断。")
    return result


class BatchProcessor:
    def __init__(self, ai_client=None, custom_prompt=None, images_per_request=None,
                 nsfw=False, nsfw_max_rolls=3, enabled_dims=None, portrait=False,
                 portrait_suffix="", max_concurrent=3, skip_completed=True):
        self.client = ai_client or get_ai_client()
        self.custom_prompt = custom_prompt
        self.images_per_request = images_per_request or config.IMAGES_PER_REQUEST
        self.nsfw = nsfw
        self.nsfw_max_rolls = nsfw_max_rolls
        self.enabled_dims = enabled_dims or DEFAULT_ENABLED_DIMS
        self.portrait = portrait
        self.portrait_suffix = portrait_suffix
        self.max_concurrent = max(1, int(max_concurrent))
        self.skip_completed = skip_completed

        # 缓存签名：影响输出的所有设置组合
        sig_raw = (f"{self.nsfw}|{self.portrait}|{self.portrait_suffix}|"
                   f"{sorted(self.enabled_dims)}|{self.custom_prompt}|"
                   f"{getattr(self.client, 'model', '')}")
        self._sig = hashlib.md5(sig_raw.encode()).hexdigest()[:10]

    # ---------- 缓存 ----------
    def _cache_path(self, img_path):
        try:
            with open(img_path, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
        except Exception:
            h = hashlib.md5(str(img_path).encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{h}_{self._sig}.txt")

    def _load_cache(self, img_path):
        p = self._cache_path(img_path)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _save_cache(self, img_path, text):
        try:
            with open(self._cache_path(img_path), "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    # ---------- 提示词 ----------
    def _build_prompt(self, count):
        if self.custom_prompt:
            p = self.custom_prompt + f"\n\n【极度重要】本次共 {count} 张图片，必须用 [IMAGE X] 格式严格分隔输出！"
            if self.nsfw:
                p += f"\n【防截断判定】完成后在新的一行输出暗号：“{END_MARKER}”"
            return p
        return build_dynamic_prompt(self.enabled_dims, self.nsfw, count, self.portrait, self.portrait_suffix)

    # ---------- 单次推理（含 Roll 重试）----------
    async def _infer_with_roll(self, compressed, prompt):
        max_attempts = self.nsfw_max_rolls + 1 if self.nsfw else 1
        raw = ""
        for attempt in range(max_attempts):
            try:
                raw = await self.client.analyze_images(compressed, prompt, nsfw=self.nsfw)
                if self.nsfw:
                    if END_MARKER in raw:
                        return clean_response(raw.replace(END_MARKER, "")), True
                    if attempt < self.nsfw_max_rolls:
                        await asyncio.sleep(1.5)
                        continue
                    return clean_response(raw), False
                return raw, True
            except Exception as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                raise e
        return raw, False

    # ---------- 处理单个 chunk（含单图降级）----------
    async def _process_chunk(self, chunk, chunk_idx, temp_dir, output_dir):
        prompt = self._build_prompt(len(chunk))

        compressed = []
        for idx, img_path in enumerate(chunk):
            comp = os.path.join(temp_dir, f"comp_{chunk_idx}_{idx}.jpg")
            compress_image_for_api(img_path, comp)
            compressed.append(comp)

        try:
            raw, _ok = await self._infer_with_roll(compressed, prompt)
            prompts = parse_batch_response(raw, len(chunk))
        except Exception as e:
            logger.warning(f"第 {chunk_idx+1} 组整体请求失败: {e}")
            prompts = [f"Error: {e}"] * len(chunk)

        # 单图降级：只对失败的图单独重跑，不拖垮整组
        failed_idx = [i for i, p in enumerate(prompts) if p.startswith("Error:")]
        if failed_idx and len(chunk) > 1:
            logger.info(f"第 {chunk_idx+1} 组有 {len(failed_idx)} 张失败，降级为单图重跑")
            single_prompt = self._build_prompt(1)
            for i in failed_idx:
                try:
                    sraw, _ = await self._infer_with_roll([compressed[i]], single_prompt)
                    prompts[i] = parse_batch_response(sraw, 1)[0]
                except Exception as e:
                    prompts[i] = f"Error: {e}"

        # 落盘 + 写缓存
        results = []
        for i, img_path in enumerate(chunk):
            p = prompts[i]
            success = not p.startswith("Error:")
            original_name = Path(img_path).name
            stem_name = Path(img_path).stem

            if success:
                shutil.copy2(img_path, os.path.join(output_dir, original_name))
                with open(os.path.join(output_dir, f"{stem_name}.txt"), "w", encoding="utf-8") as f:
                    f.write(p)
                self._save_cache(img_path, p)
                results.append(ProcessResult(original_name, p, True))
            else:
                results.append(ProcessResult(original_name, "", False, error=p.replace("Error:", "").strip()))
        return results

    # ---------- 批处理主流程 ----------
    async def process_batch(self, image_paths, output_dir, progress_callback: Optional[Callable] = None):
        temp_compress_dir = tempfile.mkdtemp()
        results_map = {}

        # 1) 断点续跑：命中缓存的直接复用
        pending = []
        skipped = 0
        for img_path in image_paths:
            if self.skip_completed:
                cached = self._load_cache(img_path)
                if cached is not None:
                    original_name = Path(img_path).name
                    stem_name = Path(img_path).stem
                    shutil.copy2(img_path, os.path.join(output_dir, original_name))
                    with open(os.path.join(output_dir, f"{stem_name}.txt"), "w", encoding="utf-8") as f:
                        f.write(cached)
                    results_map[img_path] = ProcessResult(original_name, cached, True, cached=True)
                    skipped += 1
                    continue
            pending.append(img_path)

        if skipped and progress_callback:
            progress_callback(0.0, f"⏩ 跳过 {skipped} 张已完成，剩余 {len(pending)} 张待处理")

        # 2) 并发处理剩余图片
        chunk_size = self.images_per_request
        chunks = [pending[i:i + chunk_size] for i in range(0, len(pending), chunk_size)]
        total = len(chunks)
        completed = 0
        lock = asyncio.Lock()
        sem = asyncio.Semaphore(self.max_concurrent)

        async def handle(chunk_idx, chunk):
            nonlocal completed
            async with sem:
                res = await self._process_chunk(chunk, chunk_idx, temp_compress_dir, output_dir)
            async with lock:
                completed += 1
                if progress_callback:
                    progress_callback(completed / total if total else 1.0,
                                      f"🚀 已完成 {completed}/{total} 组（并发 {self.max_concurrent}）")
            return chunk, res

        if chunks:
            tasks = [handle(i, c) for i, c in enumerate(chunks)]
            for chunk, res in await asyncio.gather(*tasks):
                for img_path, r in zip(chunk, res):
                    results_map[img_path] = r

        # 3) 按原始顺序整理结果
        results = [results_map[p] for p in image_paths if p in results_map]

        # 4) 打包
        zip_path_all = f"{output_dir}_all.zip"
        zip_path_txt = f"{output_dir}_only_txt.zip"
        with zipfile.ZipFile(zip_path_all, "w", zipfile.ZIP_DEFLATED) as zf_all, \
             zipfile.ZipFile(zip_path_txt, "w", zipfile.ZIP_DEFLATED) as zf_txt:
            for root, _, files in os.walk(output_dir):
                for f in sorted(files):
                    if f.endswith(".zip"):
                        continue
                    file_path = os.path.join(root, f)
                    zf_all.write(file_path, f)
                    if f.endswith(".txt"):
                        zf_txt.write(file_path, f)

        shutil.rmtree(temp_compress_dir, ignore_errors=True)
        return [zip_path_all, zip_path_txt], results


def process_batch_sync(input_paths, provider=None, api_key=None, base_url=None, model=None,
                       custom_prompt=None, images_per_request=None, nsfw=False, nsfw_max_rolls=3,
                       enabled_dims=None, portrait=False, portrait_suffix="",
                       max_concurrent=3, skip_completed=True, progress_callback=None):
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
                    if fi.filename.startswith('__MACOSX') or fi.filename.startswith('.'):
                        continue
                    if Path(fi.filename).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']:
                        fn = Path(fi.filename).name
                        ep = os.path.join(temp_extract_dir, fn)
                        if os.path.exists(ep):
                            ep = os.path.join(temp_extract_dir, f"{int(time.time()*1000)}_{fn}")
                        with zr.open(fi) as src, open(ep, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        final_image_paths.append(ep)
            final_image_paths.sort()
        except Exception as e:
            return None, f"❌ ZIP 解压失败: {e}", []
    else:
        final_image_paths = input_paths

    if not final_image_paths:
        return None, "❌ 未找到有效图片", []

    client = get_ai_client(provider, api_key, base_url, model)
    processor = BatchProcessor(
        ai_client=client, custom_prompt=custom_prompt, images_per_request=images_per_request,
        nsfw=nsfw, nsfw_max_rolls=nsfw_max_rolls, enabled_dims=enabled_dims or DEFAULT_ENABLED_DIMS,
        portrait=portrait, portrait_suffix=portrait_suffix,
        max_concurrent=max_concurrent, skip_completed=skip_completed
    )

    loop = asyncio.new_event_loop()
    try:
        zip_paths, results = loop.run_until_complete(
            processor.process_batch(final_image_paths, task_output_dir, progress_callback)
        )
    finally:
        loop.close()
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir, ignore_errors=True)

    gallery_data = []
    summary_lines = []
    for idx, r in enumerate(results, 1):
        saved_path = os.path.join(task_output_dir, r.filename)
        if r.success and os.path.exists(saved_path):
            gallery_data.append((saved_path, f"[{idx}] {r.filename}"))
        if r.success:
            status = "⏩" if r.cached else "✅"
        else:
            status = "❌"
        content = r.prompt if r.success else f"Error: {r.error}"
        summary_lines.append(f"{status} {r.filename}\n{'-'*40}\n{content}\n")

    summary = f"\n{'='*60}\n\n".join(summary_lines)
    return zip_paths, summary, gallery_data


# ==================== 标签扩写 ====================
def expand_tags_sync(tags, provider=None, api_key=None, base_url=None, model=None,
                     nsfw=False, nsfw_max_rolls=3, enabled_dims=None, portrait=False, portrait_suffix=""):
    if not tags.strip():
        return "❌ 请先输入需要扩写的标签或元素"

    client = get_ai_client(provider, api_key, base_url, model)
    effective_prompt = build_expansion_prompt(enabled_dims or DEFAULT_ENABLED_DIMS, nsfw, portrait, portrait_suffix)
    full_prompt = f"{effective_prompt}\n\n【用户输入的待扩写标签/元素】：\n{tags}"

    async def _run():
        max_attempts = nsfw_max_rolls + 1 if nsfw else 1
        raw_response = ""
        for attempt in range(max_attempts):
            try:
                raw_response = await client.analyze_images([], full_prompt, nsfw=nsfw)
                if nsfw:
                    if END_MARKER in raw_response:
                        raw_response = clean_response(raw_response.replace(END_MARKER, ""))
                        break
                    if attempt < nsfw_max_rolls:
                        await asyncio.sleep(1.5)
                        continue
                    raw_response = clean_response(raw_response)
                break
            except Exception as e:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                return f"❌ 扩写失败: {str(e)}"

        junk = [r'已确认.*?\n', r'好的.*?\n', r'Understood.*?\n', r'\[IMAGE 1\]\n?']
        for pat in junk:
            raw_response = re.sub(pat, '', raw_response, flags=re.IGNORECASE)
        return raw_response.strip()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()

