import os
import logging
import gradio as gr

from config import config
from processor import process_batch_sync, expand_tags_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Lucide icon SVGs (inline, no emoji anywhere)
# ─────────────────────────────────────────────────────────────────────────────
def lucide(name, size=16, cls="", stroke_width=1.8):
    icons = {
        "image": '<path d="M21 3H3a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h18a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2Z"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
        "sparkles": '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>',
        "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
        "unlock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
        "camera": '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
        "pen-tool": '<path d="m12 19 7-7 3 3-7 7-3-3z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="m2 2 7.586 7.586"/><circle cx="11" cy="11" r="2"/>',
        "sliders": '<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/>',
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
        "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
        "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
        "fast-forward": '<polygon points="13 19 22 12 13 5 13 19"/><polygon points="2 19 11 12 2 5 2 19"/>',
        "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
        "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
        "shirt": '<path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/>',
        "move": '<polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" x2="22" y1="12" y2="12"/><line x1="12" x2="12" y1="2" y2="22"/>',
        "shield-off": '<path d="m2 2 20 20"/><path d="M5 5a1 1 0 0 0-1 1v7c0 5 3.5 7.5 8 8.5a14.6 14.6 0 0 0 4-1.33"/><path d="M9.5 2.2 12 2l8 2.5v7a13 13 0 0 1-.6 3.5"/>',
        "frame": '<line x1="22" x2="2" y1="6" y2="6"/><line x1="22" x2="2" y1="18" y2="18"/><line x1="6" x2="6" y1="2" y2="22"/><line x1="18" x2="18" y1="2" y2="22"/>',
        "mountain": '<path d="m8 3 4 8 5-5 5 15H2L8 3z"/>',
        "palette": '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
        "rotate-cw": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
        "layout-grid": '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
        "file-text": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
        "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
        "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
        "alert-circle": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
        "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
        "chevron-down": '<polyline points="6 9 12 15 18 9"/>',
        "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
        "droplet": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    }
    svg_inner = icons.get(name, icons["info"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" '
        f'class="lucide {cls}" style="display:inline-block;vertical-align:middle;margin-right:6px;">'
        f'{svg_inner}</svg>'
    )


def icon_label(icon_name, text, size=15):
    return f'{lucide(icon_name, size)} {text}'


# ─────────────────────────────────────────────────────────────────────────────
# ULTRA-PREMIUM CSS
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-primary: #06080d;
    --bg-secondary: #0c1018;
    --bg-card: rgba(14, 18, 30, 0.7);
    --bg-card-hover: rgba(20, 26, 42, 0.85);
    --bg-elevated: rgba(22, 28, 45, 0.9);
    --border-subtle: rgba(255, 255, 255, 0.04);
    --border-default: rgba(255, 255, 255, 0.06);
    --border-interactive: rgba(120, 130, 255, 0.15);
    --text-primary: rgba(245, 247, 255, 0.95);
    --text-secondary: rgba(180, 190, 220, 0.75);
    --text-tertiary: rgba(140, 150, 180, 0.5);
    --accent-main: #7c6aff;
    --accent-bright: #a78bfa;
    --accent-glow: rgba(124, 106, 255, 0.12);
    --accent-warm: #f59e0b;
    --accent-rose: #fb7185;
    --accent-emerald: #34d399;
    --surface-glass: rgba(255, 255, 255, 0.02);
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-2xl: 24px;
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
    --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
    --shadow-lg: 0 8px 40px rgba(0,0,0,0.5);
    --shadow-glow: 0 0 60px rgba(124, 106, 255, 0.08);
    --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-smooth: 300ms cubic-bezier(0.4, 0, 0.2, 1);
    --transition-spring: 500ms cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* ── Global Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; }

.gradio-container {
    max-width: 1380px !important;
    margin: 0 auto !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    min-height: 100vh;
    position: relative;
}

.gradio-container::before {
    content: '';
    position: fixed;
    inset: 0;
    background:
        radial-gradient(ellipse 80% 60% at 20% 10%, rgba(124, 106, 255, 0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 80% 80%, rgba(251, 113, 133, 0.04) 0%, transparent 50%),
        radial-gradient(ellipse 50% 40% at 50% 50%, rgba(52, 211, 153, 0.03) 0%, transparent 40%);
    pointer-events: none;
    z-index: 0;
}

body, .dark { background: var(--bg-primary) !important; }

/* ── Noise Texture Overlay ── */
.gradio-container::after {
    content: '';
    position: fixed;
    inset: 0;
    opacity: 0.015;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 0;
}

/* ── Hero Header ── */
.hero-header {
    position: relative;
    padding: 48px 40px 40px;
    margin: -8px -8px 28px;
    overflow: hidden;
    border-radius: 0 0 var(--radius-2xl) var(--radius-2xl);
    background: linear-gradient(165deg, rgba(124,106,255,0.08) 0%, rgba(14,18,30,0.95) 50%, rgba(251,113,133,0.05) 100%);
    border-bottom: 1px solid var(--border-subtle);
}

.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 600px;
    height: 600px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(124,106,255,0.07) 0%, transparent 70%);
    animation: hero-pulse 8s ease-in-out infinite;
}

@keyframes hero-pulse {
    0%, 100% { transform: scale(1) translate(0, 0); opacity: 0.6; }
    50% { transform: scale(1.15) translate(-30px, 20px); opacity: 1; }
}

.hero-title {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -1.2px;
    line-height: 1.15;
    margin: 0 0 10px;
    color: var(--text-primary);
    position: relative;
}

.hero-title .accent { color: var(--accent-bright); }

.hero-subtitle {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-secondary);
    letter-spacing: 0.5px;
    margin: 0;
    position: relative;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
}

.hero-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 100px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    background: rgba(124, 106, 255, 0.1);
    color: var(--accent-bright);
    border: 1px solid rgba(124, 106, 255, 0.15);
}

/* ── Typography ── */
.gradio-container h1, .gradio-container h2, .gradio-container h3,
.gradio-container h4, .gradio-container h5 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    letter-spacing: -0.3px !important;
}

.gradio-container label, .gradio-container .label-wrap {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}

.gradio-container p, .gradio-container span {
    color: var(--text-secondary) !important;
}

/* ── Panel / Card System ── */
.gradio-container .gr-group, .gradio-container .gr-box,
.gradio-container .gr-panel, .gradio-container .panel {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
    backdrop-filter: blur(16px) saturate(1.4);
    -webkit-backdrop-filter: blur(16px) saturate(1.4);
    transition: border-color var(--transition-smooth), box-shadow var(--transition-smooth);
}

.gradio-container .gr-group:hover, .gradio-container .gr-box:hover {
    border-color: var(--border-interactive) !important;
    box-shadow: var(--shadow-glow) !important;
}

/* ── Inputs ── */
.gradio-container input[type="text"],
.gradio-container input[type="password"],
.gradio-container textarea,
.gradio-container .gr-text-input,
.gradio-container .scroll-hide {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13.5px !important;
    padding: 10px 14px !important;
    transition: all var(--transition-fast);
    caret-color: var(--accent-main);
}

.gradio-container input:focus, .gradio-container textarea:focus {
    border-color: var(--accent-main) !important;
    box-shadow: 0 0 0 3px rgba(124, 106, 255, 0.1) !important;
    outline: none !important;
}

.gradio-container input::placeholder, .gradio-container textarea::placeholder {
    color: var(--text-tertiary) !important;
}

/* ── Dropdowns ── */
.gradio-container .gr-dropdown, .gradio-container select {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    font-size: 13px !important;
}

/* ── Buttons ── */
.gradio-container button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    border-radius: var(--radius-md) !important;
    transition: all var(--transition-smooth) !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
    position: relative;
    overflow: hidden;
}

.gradio-container button::after {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 60%);
    transition: opacity var(--transition-fast);
}

.gradio-container button:hover::after { opacity: 1; }

.primary-action {
    background: linear-gradient(135deg, var(--accent-main) 0%, #6c5ce7 50%, var(--accent-rose) 100%) !important;
    background-size: 200% 200% !important;
    animation: gradient-shift 4s ease infinite !important;
    border: none !important;
    color: white !important;
    font-size: 14.5px !important;
    padding: 14px 32px !important;
    box-shadow: 0 4px 20px rgba(124, 106, 255, 0.3), 0 0 40px rgba(124, 106, 255, 0.1) !important;
    letter-spacing: 0.02em !important;
}

@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.primary-action:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(124, 106, 255, 0.4), 0 0 60px rgba(124, 106, 255, 0.15) !important;
}

.primary-action:active { transform: translateY(0) scale(0.98) !important; }

.secondary-action {
    background: rgba(124, 106, 255, 0.08) !important;
    border: 1px solid rgba(124, 106, 255, 0.2) !important;
    color: var(--accent-bright) !important;
    font-size: 13px !important;
    padding: 8px 16px !important;
}

.secondary-action:hover {
    background: rgba(124, 106, 255, 0.15) !important;
    border-color: rgba(124, 106, 255, 0.35) !important;
}

.fetch-action {
    background: rgba(52, 211, 153, 0.08) !important;
    border: 1px solid rgba(52, 211, 153, 0.2) !important;
    color: var(--accent-emerald) !important;
    font-size: 13px !important;
}

.fetch-action:hover {
    background: rgba(52, 211, 153, 0.15) !important;
    border-color: rgba(52, 211, 153, 0.35) !important;
}

.copy-action {
    background: rgba(245, 158, 11, 0.08) !important;
    border: 1px solid rgba(245, 158, 11, 0.2) !important;
    color: var(--accent-warm) !important;
    font-size: 12px !important;
    padding: 6px 14px !important;
}

.copy-action:hover {
    background: rgba(245, 158, 11, 0.15) !important;
    border-color: rgba(245, 158, 11, 0.35) !important;
}

/* ── Checkbox ── */
.gradio-container input[type="checkbox"] {
    accent-color: var(--accent-main) !important;
}

.gradio-container .gr-check-radio {
    border-color: var(--border-default) !important;
}

/* ── Accordion ── */
.gradio-container .gr-accordion {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
}

.gradio-container .gr-accordion > .label-wrap {
    padding: 14px 18px !important;
}

/* ── Tabs ── */
.gradio-container .tabs {
    background: transparent !important;
}

.gradio-container .tab-nav {
    border-bottom: 1px solid var(--border-default) !important;
    gap: 0 !important;
    background: transparent !important;
    margin-bottom: 20px;
}

.gradio-container .tab-nav button {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    color: var(--text-tertiary) !important;
    padding: 12px 24px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    border-radius: 0 !important;
    transition: all var(--transition-smooth) !important;
}

.gradio-container .tab-nav button:hover {
    color: var(--text-secondary) !important;
    background: rgba(124, 106, 255, 0.03) !important;
}

.gradio-container .tab-nav button.selected {
    color: var(--accent-bright) !important;
    border-bottom-color: var(--accent-main) !important;
    background: rgba(124, 106, 255, 0.05) !important;
}

/* ── Sliders ── */
.gradio-container input[type="range"] {
    accent-color: var(--accent-main) !important;
}

.gradio-container .rangeslider {
    background: var(--bg-secondary) !important;
}

/* ── File Upload ── */
.upload-zone {
    border: 2px dashed rgba(124, 106, 255, 0.15) !important;
    border-radius: var(--radius-xl) !important;
    background: rgba(124, 106, 255, 0.02) !important;
    transition: all var(--transition-smooth) !important;
    min-height: 140px;
}

.upload-zone:hover {
    border-color: rgba(124, 106, 255, 0.35) !important;
    background: rgba(124, 106, 255, 0.04) !important;
    box-shadow: 0 0 30px rgba(124, 106, 255, 0.06) !important;
}

/* ── Gallery ── */
.gradio-container .gr-gallery {
    border-radius: var(--radius-lg) !important;
    overflow: hidden;
}

/* ── Output Text ── */
.output-mono textarea {
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace !important;
    font-size: 12.5px !important;
    line-height: 1.75 !important;
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    padding: 16px !important;
}

/* ── Section Panels ── */
.config-panel {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-xl) !important;
    padding: 20px !important;
    backdrop-filter: blur(12px) !important;
}

.nsfw-panel {
    background: rgba(251, 113, 133, 0.03) !important;
    border: 1px solid rgba(251, 113, 133, 0.1) !important;
    border-radius: var(--radius-lg) !important;
    padding: 16px !important;
    position: relative;
    overflow: hidden;
}

.nsfw-panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-rose), transparent);
    opacity: 0.5;
}

.portrait-panel {
    background: rgba(124, 106, 255, 0.03) !important;
    border: 1px solid rgba(124, 106, 255, 0.1) !important;
    border-radius: var(--radius-lg) !important;
    padding: 16px !important;
    position: relative;
    overflow: hidden;
}

.portrait-panel::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-main), transparent);
    opacity: 0.5;
}

/* ── Info Callout ── */
.info-callout {
    font-size: 12.5px;
    color: var(--text-secondary);
    background: rgba(124, 106, 255, 0.04);
    border-radius: var(--radius-md);
    padding: 14px 18px;
    border-left: 3px solid rgba(124, 106, 255, 0.3);
    line-height: 1.6;
    margin-bottom: 16px;
}

.info-callout svg { color: var(--accent-bright); }

/* ── Section Header ── */
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}

.section-header h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    margin: 0 !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(124, 106, 255, 0.2);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(124, 106, 255, 0.35); }

/* ── File output ── */
.gradio-container .file-preview {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
}

/* ── Progress bar ── */
.gradio-container .progress-bar {
    background: linear-gradient(90deg, var(--accent-main), var(--accent-bright)) !important;
    border-radius: 100px !important;
}

/* ── Smooth entrance ── */
@keyframes fade-in-up {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
}

.gradio-container .gr-group,
.gradio-container .tabs,
.gradio-container .gr-accordion {
    animation: fade-in-up 0.5s ease-out both;
}

/* ── Focus Visible ── */
.gradio-container *:focus-visible {
    outline: 2px solid var(--accent-main) !important;
    outline-offset: 2px;
}

/* ── Hide Gradio footer ── */
footer { display: none !important; }

/* ── Dim section titles ── */
.dim-label {
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--text-tertiary) !important;
    font-weight: 600 !important;
    margin-bottom: 8px;
}
"""

# ── Clipboard JS ──
COPY_JS = "(t) => { if (t) { navigator.clipboard.writeText(t); } }"


def fetch_models_from_env():
    models = config.AVAILABLE_MODELS
    if not models:
        return gr.update(choices=[], value=None), "No models configured in AVAILABLE_MODELS"
    return gr.update(choices=models, value=models[0]), f"Loaded {len(models)} available models"


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
    if not enabled_dims:
        enabled_dims = ["appearance"]

    return safe_api_key, safe_base_url, safe_model, safe_portrait_suffix, enabled_dims


def analyze_images(files, provider, api_key, base_url, model_dropdown, model_text,
                   images_per_request, max_concurrent, skip_completed,
                   nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix, custom_prompt,
                   dim_appearance, dim_body, dim_clothing, dim_pose,
                   dim_nsfw_detail, dim_composition, dim_background, dim_style,
                   progress=gr.Progress()):
    if not files:
        return None, "Upload at least one image or a ZIP archive.", []
    input_paths = [f if isinstance(f, str) else f.name for f in files]
    safe_api_key, safe_base_url, safe_model, safe_portrait_suffix, enabled_dims = _prepare_params(
        api_key, base_url, model_dropdown, model_text, portrait_suffix,
        dim_appearance, dim_body, dim_clothing, dim_pose, dim_nsfw_detail, dim_composition, dim_background, dim_style
    )

    progress(0.0, desc="Preparing...")

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
        logger.error(f"Processing failed: {e}")
        return None, f"Processing failed: {str(e)}", []


def expand_text_tags(tags, provider, api_key, base_url, model_dropdown, model_text,
                     nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix,
                     dim_appearance, dim_body, dim_clothing, dim_pose,
                     dim_nsfw_detail, dim_composition, dim_background, dim_style):
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
        logger.error(f"Expansion failed: {e}")
        return f"Expansion failed: {str(e)}"


def on_nsfw_toggle(nsfw_on):
    if nsfw_on:
        return gr.update(value=True), gr.update(visible=True)
    return gr.update(value=False), gr.update(visible=False)


# ─────────────────────────────────────────────────────────────────────────────
# BUILD THE APP
# ─────────────────────────────────────────────────────────────────────────────
def create_gradio_app():
    with gr.Blocks(title="Prompt Engine", css=CUSTOM_CSS, theme=gr.themes.Base()) as app:

        # ── Hero Header ──
        gr.HTML(f"""
        <div class="hero-header">
            <h1 class="hero-title">
                {lucide("sparkles", 30)} Image & Tag <span class="accent">Prompt Engine</span>
            </h1>
            <p class="hero-subtitle">
                <span class="hero-tag">{lucide("zap", 11)} Concurrent</span>
                <span class="hero-tag">{lucide("fast-forward", 11)} Resume</span>
                <span class="hero-tag">{lucide("layers", 11)} Fallback</span>
                <span class="hero-tag">{lucide("pen-tool", 11)} Expand</span>
                <span class="hero-tag">{lucide("rotate-cw", 11)} Anti-Truncation</span>
            </p>
        </div>
        """)

        with gr.Row(equal_height=False):

            # ═══════════════════════════════════════════════
            #  LEFT SIDEBAR
            # ═══════════════════════════════════════════════
            with gr.Column(scale=1, min_width=320):

                # ── API Config ──
                with gr.Accordion(f"API Configuration", open=False):
                    provider = gr.Dropdown(
                        choices=["openai", "gemini", "claude", "qwen", "custom"],
                        value="openai",
                        label="Provider"
                    )
                    api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        placeholder="Leave empty to use env variable"
                    )
                    base_url = gr.Textbox(
                        label="Base URL",
                        placeholder="Leave empty to use env variable"
                    )

                    gr.HTML(f'<p class="dim-label">{lucide("layers", 11)} Model Selection</p>')
                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            choices=[], value=None,
                            label="From environment",
                            allow_custom_value=False, scale=3, filterable=False
                        )
                        fetch_btn = gr.Button(
                            "Load",
                            scale=1, elem_classes="fetch-action"
                        )
                    fetch_status = gr.Textbox(label="", interactive=False, max_lines=1, show_label=False)
                    model_text = gr.Textbox(
                        label="Manual override",
                        placeholder="e.g. gpt-4o (takes priority)"
                    )

                # ── Portrait Mode ──
                with gr.Group(elem_classes="portrait-panel"):
                    gr.HTML(f'<div class="section-header"><h3>{lucide("camera", 16)} Portrait Annotation</h3></div>')
                    portrait_mode = gr.Checkbox(
                        label="Enable objective portrait mode (recommended for LoRA training)",
                        value=False
                    )
                    portrait_suffix = gr.Textbox(
                        label="Subject suffix token",
                        placeholder='e.g. octopus -> "a young woman octopus"'
                    )

                # ── NSFW & Dimensions ──
                with gr.Group(elem_classes="nsfw-panel"):
                    gr.HTML(f'<div class="section-header"><h3>{lucide("unlock", 16)} NSFW & Dimension Control</h3></div>')
                    nsfw_mode = gr.Checkbox(
                        label="Enable unrestricted NSFW mode",
                        value=False,
                        info="Multi-layer bypass + anti-truncation roll retry"
                    )
                    nsfw_max_rolls = gr.Slider(
                        minimum=0, maximum=10, value=3, step=1,
                        label="Auto-retry (roll) on truncation",
                        visible=False
                    )

                    with gr.Accordion(f"Dimension Toggles", open=False):
                        gr.HTML(f'<div class="info-callout">{lucide("info", 13)} Disabled dimensions are strictly forbidden in output. Affects both image captioning and tag expansion.</div>')
                        with gr.Row():
                            with gr.Column(min_width=140):
                                dim_appearance = gr.Checkbox(label="Appearance", value=True)
                                dim_body = gr.Checkbox(label="Body Detail", value=True)
                                dim_clothing = gr.Checkbox(label="Clothing", value=True)
                                dim_pose = gr.Checkbox(label="Pose / Action", value=True)
                            with gr.Column(min_width=140):
                                dim_nsfw_detail = gr.Checkbox(label="NSFW Detail", value=False)
                                dim_composition = gr.Checkbox(label="Composition", value=True)
                                dim_background = gr.Checkbox(label="Background", value=True)
                                dim_style = gr.Checkbox(label="Art Style", value=True)

            # ═══════════════════════════════════════════════
            #  MAIN CONTENT
            # ═══════════════════════════════════════════════
            with gr.Column(scale=2):
                with gr.Tabs():

                    # ── Tab 1: Image Captioning ──
                    with gr.TabItem(f"Image Captioning"):
                        with gr.Row():
                            images_per_request = gr.Slider(
                                minimum=1, maximum=15, value=5, step=1,
                                label="Images per request",
                                info="Recommended 3-5"
                            )
                            max_concurrent = gr.Slider(
                                minimum=1, maximum=8, value=3, step=1,
                                label="Concurrency",
                                info="Higher = faster, watch rate limits"
                            )
                        skip_completed = gr.Checkbox(
                            label="Skip completed (resume from cache when same image + same config)",
                            value=True
                        )

                        custom_prompt = gr.Textbox(
                            label="Custom prompt template (optional)",
                            lines=2,
                            placeholder="Overrides all mode/dimension settings above (image captioning only)"
                        )

                        file_input = gr.Files(
                            label="Upload images or .zip archive",
                            file_types=["image", ".zip"],
                            file_count="multiple",
                            elem_classes="upload-zone"
                        )

                        submit_btn = gr.Button(
                            "Start Processing",
                            variant="primary", size="lg",
                            elem_classes="primary-action"
                        )

                        output_file = gr.File(
                            label="Downloads (full package & text-only package)",
                            file_count="multiple"
                        )

                        with gr.Accordion("Gallery Preview", open=False):
                            output_gallery = gr.Gallery(
                                label="Results",
                                columns=4, rows=2, height="auto",
                                object_fit="contain", preview=True
                            )

                        with gr.Row(elem_classes="section-header"):
                            gr.HTML(f'<h3>{lucide("file-text", 16)} Text Summary</h3>')
                            copy_summary_btn = gr.Button(
                                "Copy All",
                                scale=0, elem_classes="copy-action"
                            )
                        output_summary = gr.Textbox(
                            label="Combined output for all images",
                            lines=15, interactive=False,
                            elem_classes="output-mono"
                        )

                    # ── Tab 2: Tag Expansion ──
                    with gr.TabItem(f"Tag Expansion"):
                        gr.HTML(f"""
                        <div class="info-callout">
                            {lucide("info", 14)}
                            <strong>Tag Expansion</strong> — Enter simple element tags and the AI will expand them
                            into a richly detailed description based on your dimension and mode settings.
                        </div>
                        """)

                        tags_input = gr.Textbox(
                            label="Input base tags or elements",
                            lines=4,
                            placeholder="e.g. 1girl, forest, mage, night..."
                        )

                        expand_btn = gr.Button(
                            "Expand Prompt",
                            variant="primary", size="lg",
                            elem_classes="primary-action"
                        )

                        with gr.Row(elem_classes="section-header"):
                            gr.HTML(f'<h3>{lucide("sparkles", 16)} Expansion Result</h3>')
                            copy_expand_btn = gr.Button(
                                "Copy Result",
                                scale=0, elem_classes="copy-action"
                            )
                        expand_output = gr.Textbox(
                            label="",
                            lines=12, interactive=False,
                            elem_classes="output-mono"
                        )

        # ═══════════════════════════════════════════════
        #  EVENT BINDINGS
        # ═══════════════════════════════════════════════
        nsfw_mode.change(
            fn=on_nsfw_toggle,
            inputs=[nsfw_mode],
            outputs=[dim_nsfw_detail, nsfw_max_rolls]
        )

        fetch_btn.click(
            fn=fetch_models_from_env,
            inputs=[],
            outputs=[model_dropdown, fetch_status]
        )

        submit_btn.click(
            fn=analyze_images,
            inputs=[
                file_input, provider, api_key, base_url, model_dropdown, model_text,
                images_per_request, max_concurrent, skip_completed,
                nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix, custom_prompt,
                dim_appearance, dim_body, dim_clothing, dim_pose,
                dim_nsfw_detail, dim_composition, dim_background, dim_style
            ],
            outputs=[output_file, output_summary, output_gallery],
        )

        expand_btn.click(
            fn=expand_text_tags,
            inputs=[
                tags_input, provider, api_key, base_url, model_dropdown, model_text,
                nsfw_mode, nsfw_max_rolls, portrait_mode, portrait_suffix,
                dim_appearance, dim_body, dim_clothing, dim_pose,
                dim_nsfw_detail, dim_composition, dim_background, dim_style
            ],
            outputs=[expand_output]
        )

        copy_summary_btn.click(fn=None, inputs=[output_summary], outputs=None, js=COPY_JS)
        copy_expand_btn.click(fn=None, inputs=[expand_output], outputs=None, js=COPY_JS)

    return app


if __name__ == "__main__":
    app = create_gradio_app()
    auth_users = config.AUTH_USERS
    if auth_users:
        def auth_fn(username, password):
            return any(username == u and password == p for u, p in auth_users)
        app.launch(
            server_name="0.0.0.0", server_port=7860, share=False,
            auth=auth_fn, auth_message="Authentication required"
        )
    else:
        app.launch(server_name="0.0.0.0", server_port=7860, share=False)
