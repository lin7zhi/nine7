import os
import logging
import gradio as gr

from config import config
from processor import process_batch_sync, expand_tags_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

CUSTOM_CSS = """
.gradio-container { max-width: 1200px !important; font-family: 'Inter', sans-serif !important; }
.title-block {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px; padding: 28px 32px; margin-bottom: 20px;
    color: white; text-align: center;
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);
}
.title-block h1 { font-size: 28px; font-weight: 700; margin: 0 0 8px 0; letter-spacing: -0.5px; }
.title-block p { font-size: 14px; opacity: 0.9; margin: 0; }
.primary-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    border: none !important; border-radius: 12px !important; color: white !important;
    font-weight: 600 !important; font-size: 16px !important; padding: 14px 28px !important;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.35) !important; transition: all 0.3s ease !important;
}
.primary-btn:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5) !important; }
.nsfw-toggle {
    border: 1px solid rgba(255, 107, 107, 0.3) !important; border-radius: 10px !important;
    padding: 12px !important; background: rgba(255, 107, 107, 0.05) !important;
}
.mode-toggle-portrait {
    border: 1px solid rgba(102, 126, 234, 0.3) !important; border-radius: 10px !important;
    padding: 12px !important; background: rgba(102, 126, 234, 0.05) !important; margin-bottom: 10px;
}
.tip-text {
    font-size: 13px; color: rgba(156, 163, 175, 0.9); background: rgba(102, 126, 234, 0.08);
    border-radius: 10px; padding: 12px 16px; border-left: 3px solid rgba(102, 126, 234, 0.5); margin-bottom: 15px;
}
.warning-text { font-size: 12px; color: #ef4444; margin-top: 4px; font-weight: bold; }
.summary-box textarea { font-family: 'JetBrains Mono', Consolas, monospace !important; font-size: 13px !important; line-height: 1.6 !important; border-radius: 10px !important; }
.upload-area { border: 2px dashed rgba(102, 126, 234, 0.3) !important; border-radius: 14px !important; transition: all 0.3s ease !important; }
.upload-area:hover { border-color: rgba(102, 126, 234, 0.6) !important; background: rgba(102, 126, 234, 0.05) !important; }
.fetch-btn {
    background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%) !important;
    border: none !important; color: #1a1a2e !important; font-weight: 600 !important;
}
.copy-btn {
    background: linear-gradient(135deg, #f6d365 0%, #fda085 100%) !important;
    border: none !important; color: #7a3e00 !important; font-weight: 600 !important;
}
"""

# 复制到剪贴板的 JS
COPY_JS = "(t) => { if (t) { navigator.clipboard.writeText(t); } }"


def fetch_models_from_env():
    models = config.AVAILABLE_MODELS
    if not models:
        return gr.update(choices=[], value=None), "⚠️ HF 环境变量 AVAILABLE_MODELS 未配置或为空"
    return gr.update(choices=models, value=models[0]), f"✅ 已读取到 {len(models)} 个可用模型"


def _prepare_params(api_key, base_url, model_dropdown, model_text, portrait_suffix,
                    dim_appearance, dim_body, dim_clothing, dim_pose,
                    dim_nsfw_detail, dim_composition, dim_background, dim_style):
    safe_api_key = (api_key or "").strip() or None
    safe_base_url = (base_url or "").strip() or None
    safe_model = (model_text or "").strip() or (model_dropdown or "").strip() or None
    safe_portrait_suffix = (portrait_suffix or "").strip()

    enabled_dims = []
    if dim_appearance: enabled_dims.append("appearance")
    if dim_body: enabled_dims.append("body")
    if dim_clothing: enabled_dims.append("clothing")
    if dim_pose: enabled_dims.append("pose")
    if dim_nsfw_detail: enabled_dims.append("nsfw_detail")
    if dim_composition: enabled_dims.append("composition")
    if dim_background: enabled_dims.append("background")
    if dim_style: enabled_dims.append("style")
    if not enabled_dims: enabled_dims = ["appearance"]

    return safe_api_key, safe_base_url, safe_model, safe_portrait_suffix, enabled_dims


def analyze_images(files, provider, api_key, base_url, model_dropdown, model_text,
                   images_per_request, max_concurrent, skip_completed,
                   nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix, custom_prompt,
                   dim_appearance, dim_body, dim_clothing, dim_pose,
                   dim_nsfw_detail, dim_composition, dim_background, dim_style,
                   progress=gr.Progress()):
    if not files:
        return None, "❌ 请上传至少一张图片或一个 ZIP 压缩包", []
    input_paths = [f if isinstance(f, str) else f.name for f in files]
    safe_api_key, safe_base_url, safe_model, safe_portrait_suffix, enabled_dims = _prepare_params(
        api_key, base_url, model_dropdown, model_text, portrait_suffix,
        dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style
    )

    progress(0.0, desc="准备中...")

    def cb(frac, desc):
        try:
            progress(frac, desc=desc)
        except Exception:
            pass

    try:
        zip_paths, summary, gallery_data = process_batch_sync(
            input_paths=input_paths, provider=provider, api_key=safe_api_key, base_url=safe_base_url, model=safe_model,
            custom_prompt=(custom_prompt or "").strip() or None, images_per_request=int(images_per_request),
            nsfw=nsfw_mode, nsfw_max_rolls=int(nsfw_max_rolls), enabled_dims=enabled_dims,
            portrait=portrait_mode, portrait_suffix=safe_portrait_suffix,
            max_concurrent=int(max_concurrent), skip_completed=skip_completed,
            progress_callback=cb
        )
        return zip_paths, summary, gallery_data
    except Exception as e:
        logger.error(f"反推失败: {e}")
        return None, f"❌ 处理失败: {str(e)}", []


def expand_text_tags(tags, provider, api_key, base_url, model_dropdown, model_text,
                     nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix,
                     dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style):
    safe_api_key, safe_base_url, safe_model, safe_portrait_suffix, enabled_dims = _prepare_params(
        api_key, base_url, model_dropdown, model_text, portrait_suffix,
        dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style
    )
    try:
        return expand_tags_sync(
            tags=tags, provider=provider, api_key=safe_api_key, base_url=safe_base_url, model=safe_model,
            nsfw=nsfw_mode, nsfw_max_rolls=int(nsfw_max_rolls), enabled_dims=enabled_dims,
            portrait=portrait_mode, portrait_suffix=safe_portrait_suffix
        )
    except Exception as e:
        logger.error(f"扩写失败: {e}")
        return f"❌ 扩写失败: {str(e)}"


def on_nsfw_toggle(nsfw_on):
    if nsfw_on:
        return gr.update(value=True), gr.update(visible=True)
    return gr.update(value=False), gr.update(visible=False)


def create_gradio_app():
    with gr.Blocks(title="🖼️ Image & Tag to Prompt") as app:
        gr.HTML(f"<style>{CUSTOM_CSS}</style>")

        gr.HTML("""
        <div class="title-block">
            <h1>🖼️ Image / Tag → Prompt 智能提示词引擎</h1>
            <p>并发处理 · 断点续跑 · 单图降级 · 标签扩写 · NSFW 防截断 Roll</p>
        </div>
        """)

        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=320):

                with gr.Accordion("⚙️ API 设置", open=False):
                    provider = gr.Dropdown(choices=["openai", "gemini", "claude", "qwen", "custom"], value="openai", label="AI 提供商")
                    api_key = gr.Textbox(label="API Key", type="password", placeholder="留空→使用环境变量")
                    base_url = gr.Textbox(label="API Base URL", placeholder="留空→使用环境变量")

                    gr.Markdown("##### 模型选择")
                    with gr.Row():
                        model_dropdown = gr.Dropdown(choices=[], value=None, label="从环境变量选择", allow_custom_value=True, scale=3)
                        fetch_btn = gr.Button("🔍 获取模型", scale=1, elem_classes="fetch-btn")
                    fetch_status = gr.Textbox(label="", interactive=False, max_lines=1, show_label=False)
                    model_text = gr.Textbox(label="或手动输入", placeholder="如 gpt-4o（优先读取此处）")

                with gr.Group(elem_classes="mode-toggle-portrait"):
                    gr.Markdown("### 📸 肖像标注模式")
                    portrait_mode = gr.Checkbox(label="启用客观肖像标注 (训练 Lora 推荐)", value=False, info="覆盖下方维度开关，只输出客观短词。")
                    portrait_suffix = gr.Textbox(label="自定义人物后缀【XX】", placeholder="例：章鱼 → 「一个年轻女性章鱼」")

                with gr.Group(elem_classes="nsfw-toggle"):
                    gr.Markdown("### 🔓 NSFW 破限与维度控制")
                    nsfw_mode = gr.Checkbox(label="🔞 启用 NSFW 无限制模式", value=False, info="多层破限 + 防截断 Roll 重试")
                    nsfw_max_rolls = gr.Slider(minimum=0, maximum=10, value=3, step=1, label="🔄 触发截断自动重跑 (Roll) 次数", visible=False)

                    with gr.Accordion("🎛️ 描述维度开关（点击展开）", open=False):
                        gr.Markdown("*关闭维度会强硬禁止AI描述该项，【反推】和【扩写】均生效。*")
                        with gr.Row():
                            with gr.Column(min_width=140):
                                dim_appearance = gr.Checkbox(label="👤 人物外观", value=True)
                                dim_body = gr.Checkbox(label="🫧 身体细节", value=True)
                                dim_clothing = gr.Checkbox(label="👗 服装状态", value=True)
                                dim_pose = gr.Checkbox(label="🤸 姿势动作", value=True)
                            with gr.Column(min_width=140):
                                dim_nsfw_detail = gr.Checkbox(label="🔞 性相关细节", value=False)
                                dim_composition = gr.Checkbox(label="📐 构图镜头", value=True)
                                dim_background = gr.Checkbox(label="🏞️ 背景环境", value=True)
                                dim_style = gr.Checkbox(label="🎨 画风质量", value=True)

            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.TabItem("🖼️ 图像反推"):
                        with gr.Row():
                            images_per_request = gr.Slider(minimum=1, maximum=15, value=5, step=1, label="单次合并图片数", info="建议 3~5")
                            max_concurrent = gr.Slider(minimum=1, maximum=8, value=3, step=1, label="并发请求数", info="越大越快，注意限流")
                        skip_completed = gr.Checkbox(label="⏩ 跳过已完成（断点续跑，相同图+相同设置直接复用缓存）", value=True)

                        custom_prompt = gr.Textbox(label="📝 完全自定义模板 (可选)", lines=2, placeholder="填写后将完全覆盖上方所有模式和开关（仅图像反推生效）")

                        file_input = gr.Files(label="上传图片或 .zip 压缩包", file_types=["image", ".zip"], file_count="multiple", elem_classes="upload-area")
                        submit_btn = gr.Button("🚀 开始极速反推", variant="primary", size="lg", elem_classes="primary-btn")

                        output_file = gr.File(label="📦 下载区域 (原图+TXT 包 及 纯 TXT 轻量包)", file_count="multiple")

                        with gr.Accordion("🖼️ 图文对照画廊预览 (点击展开)", open=False):
                            output_gallery = gr.Gallery(label="处理结果预览", columns=4, rows=2, height="auto", object_fit="contain", preview=True)

                        with gr.Row():
                            gr.Markdown("### 📊 纯文本对照摘要")
                            copy_summary_btn = gr.Button("📋 复制全部", scale=0, elem_classes="copy-btn")
                        output_summary = gr.Textbox(label="所有图片描述合并结果", lines=15, interactive=False, elem_classes="summary-box")

                    with gr.TabItem("✍️ 标签元素扩写"):
                        gr.HTML("""<div class="tip-text">💡 <b>扩写说明：</b>输入简单元素标签，AI 根据左侧<b>【维度开关】</b>和<b>【NSFW/肖像模式】</b>扩写成细节饱满的中文长段落。</div>""")
                        tags_input = gr.Textbox(label="输入基础标签或元素", lines=4, placeholder="例如：1girl, 森林, 魔法师, 夜晚...")
                        expand_btn = gr.Button("✨ 开始扩写提示词", variant="primary", size="lg", elem_classes="primary-btn")

                        with gr.Row():
                            gr.Markdown("### 扩写结果")
                            copy_expand_btn = gr.Button("📋 复制结果", scale=0, elem_classes="copy-btn")
                        expand_output = gr.Textbox(label="", lines=12, interactive=False, elem_classes="summary-box")

        # ===== 事件绑定 =====
        nsfw_mode.change(fn=on_nsfw_toggle, inputs=[nsfw_mode], outputs=[dim_nsfw_detail, nsfw_max_rolls])
        fetch_btn.click(fn=fetch_models_from_env, inputs=[], outputs=[model_dropdown, fetch_status])

        submit_btn.click(
            fn=analyze_images,
            inputs=[
                file_input, provider, api_key, base_url, model_dropdown, model_text,
                images_per_request, max_concurrent, skip_completed,
                nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix, custom_prompt,
                dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style
            ],
            outputs=[output_file, output_summary, output_gallery],
        )

        expand_btn.click(
            fn=expand_text_tags,
            inputs=[
                tags_input, provider, api_key, base_url, model_dropdown, model_text,
                nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix,
                dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style
            ],
            outputs=[expand_output]
        )

        # 一键复制（纯前端 JS，不走后端）
        copy_summary_btn.click(fn=None, inputs=[output_summary], outputs=None, js=COPY_JS)
        copy_expand_btn.click(fn=None, inputs=[expand_output], outputs=None, js=COPY_JS)

    return app


if __name__ == "__main__":
    app = create_gradio_app()
    auth_users = config.AUTH_USERS
    if auth_users:
        def auth_fn(username, password):
            return any(username == u and password == p for u, p in auth_users)
        app.launch(server_name="0.0.0.0", server_port=7860, share=False,
                   auth=auth_fn, auth_message="🔒 请输入账号密码登录后使用")
    else:
        app.launch(server_name="0.0.0.0", server_port=7860, share=False)

